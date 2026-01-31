"""
MCP RSS Server - Exposes RSS feed fetching as MCP tools.

This server can be used by any MCP client (LangGraph agent, Claude Desktop, etc.)
to fetch and parse RSS feeds.

Usage:
    # Run as MCP server (stdio transport)
    python src/mcp_rss_server.py

    # Test mode
    python src/mcp_rss_server.py --test
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from models import Article

logger = logging.getLogger(__name__)

# Create MCP server instance
server = Server("rss-news-server")


def load_sources_config() -> dict:
    """Load RSS feed sources from config/sources.yaml."""
    config_path = Path(__file__).parent.parent / "config" / "sources.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def parse_published_date(entry: Any) -> datetime | None:
    """Parse publication date from RSS entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass

    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass

    return None


def is_fresh(published: datetime | None, hours: int) -> bool:
    """Check if article is within freshness window."""
    if published is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return published >= cutoff


def fetch_single_feed(
    feed_url: str,
    topic: str,
    max_articles: int = 50,
    freshness_hours: int = 24,
) -> list[Article]:
    """Fetch articles from a single RSS feed."""
    logger.info(f"Fetching: {feed_url}")

    try:
        feed = feedparser.parse(feed_url)

        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Feed parse warning: {feed.bozo_exception}")

        articles = []
        source_name = feed.feed.get("title", feed_url)

        for entry in feed.entries[:max_articles]:
            published = parse_published_date(entry)

            if not is_fresh(published, freshness_hours):
                continue

            article = Article(
                title=entry.get("title", "No title"),
                link=entry.get("link", ""),
                summary=entry.get("summary", entry.get("description", "")),
                source=source_name,
                topic=topic,
                published=published,
            )
            articles.append(article)

        logger.info(f"  -> {len(articles)} articles from {source_name}")
        return articles

    except Exception as e:
        logger.error(f"Failed to fetch {feed_url}: {e}")
        return []


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="fetch_feeds",
            description="Fetch articles from RSS feeds. Can fetch all topics or filter by specific ones.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Topics to fetch (e.g., ['ai', 'software']). Empty for all.",
                    },
                    "max_articles_per_feed": {
                        "type": "integer",
                        "description": "Max articles per feed (default: 50)",
                        "default": 50,
                    },
                    "freshness_hours": {
                        "type": "integer",
                        "description": "Only articles from last N hours (default: 24)",
                        "default": 24,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="list_topics",
            description="List all available news topics.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle MCP tool calls."""

    if name == "list_topics":
        config = load_sources_config()
        topics = list(config.get("rss_feeds", {}).keys())
        return [TextContent(type="text", text=json.dumps({"topics": topics}))]

    elif name == "fetch_feeds":
        topics_filter = arguments.get("topics", [])
        max_articles = arguments.get("max_articles_per_feed", 50)
        freshness_hours = arguments.get("freshness_hours", 24)

        config = load_sources_config()
        rss_feeds = config.get("rss_feeds", {})

        if topics_filter:
            rss_feeds = {k: v for k, v in rss_feeds.items() if k in topics_filter}

        all_articles = []
        for topic, feed_urls in rss_feeds.items():
            for feed_url in feed_urls:
                articles = fetch_single_feed(
                    feed_url, topic, max_articles, freshness_hours
                )
                all_articles.extend(articles)

        articles_data = [a.to_dict() for a in all_articles]

        return [TextContent(
            type="text",
            text=json.dumps({"count": len(articles_data), "articles": articles_data}, default=str)
        )]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run_server():
    """Run MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def test_mode():
    """Test RSS fetching without MCP protocol."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("Testing MCP RSS Server...\n")

    config = load_sources_config()
    settings = config.get("settings", {})
    freshness_hours = settings.get("freshness_hours", 24)
    rss_feeds = config.get("rss_feeds", {})

    total = 0
    for topic, feed_urls in rss_feeds.items():
        if feed_urls:
            articles = fetch_single_feed(
                feed_urls[0], topic, max_articles=5, freshness_hours=freshness_hours
            )
            total += len(articles)

            print(f"\n[{topic.upper()}] {len(articles)} articles:")
            for a in articles[:3]:
                print(f"  - {a.title[:60]}...")

    print(f"\n{'='*50}")
    print(f"Total: {total} articles fetched from {len(rss_feeds)} topics")
    print("MCP server test: OK")


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        test_mode()
    else:
        asyncio.run(run_server())