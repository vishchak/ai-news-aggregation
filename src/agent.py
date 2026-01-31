"""
LangGraph agent for news digest orchestration.

Connects to MCP RSS server, scores articles with Ollama, formats and sends digest.
"""

import asyncio
import json
import logging
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from models import Article
from tools.ollama_tools import (
    check_ollama_available,
    get_llm,
    load_user_interests,
    score_and_summarize_article,
)

logger = logging.getLogger(__name__)


class DigestState(TypedDict):
    """State that flows through the digest pipeline."""
    raw_articles: list[dict]
    scored_articles: list[dict]
    digest_markdown: str
    digest_html: str
    min_score: float
    max_articles: int | None
    dry_run: bool
    error: str | None
    stats: dict


class MCPClient:
    """Client for communicating with MCP RSS server."""

    def __init__(self):
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def connect(self):
        """Connect to the MCP RSS server."""
        server_path = Path(__file__).parent / "mcp_rss_server.py"

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(server_path)],
            env=None,
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        await self.session.initialize()
        logger.info("Connected to MCP RSS server")

    async def fetch_feeds(
        self,
        topics: list[str] | None = None,
        max_articles_per_feed: int = 50,
        freshness_hours: int = 24,
    ) -> list[dict]:
        """Fetch articles via MCP tool call."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        arguments = {
            "topics": topics or [],
            "max_articles_per_feed": max_articles_per_feed,
            "freshness_hours": freshness_hours,
        }

        result = await self.session.call_tool("fetch_feeds", arguments)

        # Parse response
        if result.content and len(result.content) > 0:
            text = result.content[0].text
            data = json.loads(text)
            return data.get("articles", [])

        return []

    async def close(self):
        """Close the MCP connection."""
        await self.exit_stack.aclose()


async def fetch_node(state: DigestState, mcp_client: MCPClient) -> dict:
    """Fetch articles from MCP RSS server."""
    logger.info("Fetching articles via MCP...")

    try:
        articles = await mcp_client.fetch_feeds()
        logger.info(f"Fetched {len(articles)} raw articles")

        return {
            "raw_articles": articles,
            "stats": {**state.get("stats", {}), "fetched": len(articles)},
        }
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return {"error": f"Fetch failed: {e}"}


def dedupe_articles(articles: list[dict], threshold: int = 85) -> list[dict]:
    """Remove duplicate articles by title similarity."""
    from rapidfuzz import fuzz

    if not articles:
        return []

    unique = []
    seen_titles = []

    for article in articles:
        title = article.get("title", "")
        is_dupe = False

        for seen in seen_titles:
            if fuzz.ratio(title.lower(), seen.lower()) >= threshold:
                is_dupe = True
                break

        if not is_dupe:
            unique.append(article)
            seen_titles.append(title)

    return unique


def score_node(state: DigestState) -> dict:
    """Score and summarize articles using Ollama."""
    articles = state.get("raw_articles", [])
    min_score = state.get("min_score", 6.0)
    max_articles = state.get("max_articles")

    # Deduplicate first
    articles = dedupe_articles(articles)
    logger.info(f"After dedup: {len(articles)} articles")

    # Limit for testing
    if max_articles:
        articles = articles[:max_articles]

    logger.info(f"Scoring {len(articles)} articles with Ollama...")

    try:
        check_ollama_available()
    except ConnectionError as e:
        logger.error(str(e))
        return {"error": str(e)}

    interests = load_user_interests()
    llm = get_llm()

    scored = []
    for i, article in enumerate(articles, 1):
        title = article.get("title", "")
        logger.info(f"  [{i}/{len(articles)}] {title[:50]}...")

        score, summary = score_and_summarize_article(
            title=title,
            content=article.get("summary", ""),
            source=article.get("source", ""),
            interests=interests,
            llm=llm,
        )

        article["score"] = score
        article["ai_summary"] = summary

        if score >= min_score:
            scored.append(article)
            logger.info(f"    Score: {score:.1f} - INCLUDED")
        else:
            logger.debug(f"    Score: {score:.1f} - filtered")

    scored.sort(key=lambda a: a.get("score", 0), reverse=True)

    logger.info(f"Scoring complete: {len(scored)} articles passed")

    return {
        "scored_articles": scored,
        "stats": {
            **state.get("stats", {}),
            "after_dedupe": len(articles),
            "passed_filter": len(scored),
        },
    }


def format_node(state: DigestState) -> dict:
    """Format articles into Markdown and HTML digest."""
    from datetime import datetime

    articles = state.get("scored_articles", [])
    logger.info(f"Formatting digest with {len(articles)} articles...")

    if not articles:
        empty_md = "# Daily News Digest\n\nNo relevant articles found today."
        return {
            "digest_markdown": empty_md,
            "digest_html": f"<h1>Daily News Digest</h1><p>No relevant articles found.</p>",
        }

    # Group by topic
    by_topic: dict[str, list] = {}
    for article in articles:
        topic = article.get("topic", "general").upper()
        if topic not in by_topic:
            by_topic[topic] = []
        by_topic[topic].append(article)

    # Build Markdown
    today = datetime.now().strftime("%A, %B %d, %Y")
    md_parts = [f"# Daily News Digest\n*{today}*\n"]

    for topic, topic_articles in by_topic.items():
        md_parts.append(f"\n## {topic}\n")

        for article in topic_articles:
            title = article.get("title", "Untitled")
            link = article.get("link", "#")
            source = article.get("source", "Unknown")
            score = article.get("score", 0)
            summary = article.get("ai_summary") or article.get("summary", "")[:200]

            md_parts.append(f"### [{title}]({link})")
            md_parts.append(f"*{source}* | Score: {score:.1f}\n")
            md_parts.append(f"{summary}\n")

    markdown = "\n".join(md_parts)

    # Convert to HTML
    html = _markdown_to_html(markdown)

    return {"digest_markdown": markdown, "digest_html": html}


def _markdown_to_html(markdown: str) -> str:
    """Simple Markdown to HTML conversion with inline styles."""
    import re

    html = markdown

    # Headers
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.M)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.M)
    html = re.sub(r"^### \[(.+?)\]\((.+?)\)$", r"<h3><a href='\2'>\1</a></h3>", html, flags=re.M)

    # Emphasis
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Links
    html = re.sub(r"\[(.+?)\]\((.+?)\)", r"<a href='\2'>\1</a>", html)

    # Line breaks to paragraphs
    html = re.sub(r"\n\n+", "</p><p>", html)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
h1 {{ color: #333; }} h2 {{ color: #555; border-bottom: 1px solid #ddd; }} h3 {{ margin-bottom: 5px; }}
a {{ color: #0066cc; }} em {{ color: #666; }}
</style>
</head>
<body><p>{html}</p></body>
</html>"""


def send_node(state: DigestState) -> dict:
    """Send digest via email."""
    dry_run = state.get("dry_run", False)

    if dry_run:
        logger.info("Dry run - skipping email")
        return {"stats": {**state.get("stats", {}), "email_sent": False}}

    try:
        from sender import send_digest

        html = state.get("digest_html", "")
        success = send_digest(html)
        return {"stats": {**state.get("stats", {}), "email_sent": success}}
    except ImportError:
        logger.warning("Sender module not available")
        return {"stats": {**state.get("stats", {}), "email_sent": False}}
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return {"error": f"Email failed: {e}"}


def build_graph():
    """Build the LangGraph pipeline."""
    graph = StateGraph(DigestState)

    graph.add_node("score", score_node)
    graph.add_node("format", format_node)
    graph.add_node("send", send_node)

    graph.add_edge(START, "score")
    graph.add_edge("score", "format")
    graph.add_edge("format", "send")
    graph.add_edge("send", END)

    return graph.compile()


async def run_pipeline(
    dry_run: bool = False,
    min_score: float = 6.0,
    max_articles: int | None = None,
) -> DigestState:
    """Run the full digest pipeline."""
    logger.info("Starting news digest pipeline...")

    # Connect to MCP server and fetch
    mcp_client = MCPClient()

    try:
        await mcp_client.connect()

        # Fetch articles
        initial_state: DigestState = {
            "raw_articles": [],
            "scored_articles": [],
            "digest_markdown": "",
            "digest_html": "",
            "min_score": min_score,
            "max_articles": max_articles,
            "dry_run": dry_run,
            "error": None,
            "stats": {},
        }

        fetch_result = await fetch_node(initial_state, mcp_client)
        initial_state.update(fetch_result)

        if initial_state.get("error"):
            return initial_state

        # Run rest of pipeline synchronously
        graph = build_graph()
        result = graph.invoke(initial_state)

        logger.info(f"Pipeline complete. Stats: {result.get('stats', {})}")
        return result

    finally:
        await mcp_client.close()


def main():
    """CLI entry point."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run news digest agent")
    parser.add_argument("--dry-run", action="store_true", help="Don't send email")
    parser.add_argument("--test", action="store_true", help="Process only 3 articles")
    parser.add_argument("--min-score", type=float, default=6.0, help="Minimum score")
    args = parser.parse_args()

    result = asyncio.run(run_pipeline(
        dry_run=args.dry_run,
        min_score=args.min_score,
        max_articles=3 if args.test else None,
    ))

    if result.get("error"):
        print(f"\nError: {result['error']}")
        sys.exit(1)

    print(f"\nStats: {result.get('stats', {})}")
    print(f"\n{'='*60}")
    print("DIGEST PREVIEW")
    print(f"{'='*60}\n")
    print(result.get("digest_markdown", "No content"))


if __name__ == "__main__":
    main()