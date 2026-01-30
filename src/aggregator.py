"""
RSS feed aggregator for news collection.

Fetches articles from RSS feeds defined in config/sources.yaml,
parses them into a standardized format, and filters to last 24 hours.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import feedparser
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Standardized article representation across all sources."""

    title: str
    link: str
    summary: str
    source: str
    topic: str
    published: Optional[datetime] = None
    score: float = 0.0
    ai_summary: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "link": self.link,
            "summary": self.summary,
            "source": self.source,
            "topic": self.topic,
            "published": self.published.isoformat() if self.published else None,
            "score": self.score,
            "ai_summary": self.ai_summary,
        }


def load_sources_config() -> dict:
    """
    Load RSS feed sources from config/sources.yaml.

    Returns:
        Dictionary with 'rss_feeds' mapping topics to feed URLs.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If config file is malformed.
    """
    config_path = Path(__file__).parent.parent / "config" / "sources.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    logger.debug(f"Loaded sources config from {config_path}")
    return config


def parse_published_date(entry: dict) -> Optional[datetime]:
    """
    Parse publication date from RSS entry.

    Args:
        entry: feedparser entry dictionary.

    Returns:
        Timezone-aware datetime or None if parsing fails.
    """
    # feedparser provides parsed date as time_struct in 'published_parsed'
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            # Convert time.struct_time to datetime (assumes UTC)
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError) as e:
            logger.debug(f"Failed to parse published_parsed: {e}")

    # Fallback: try 'updated_parsed'
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError) as e:
            logger.debug(f"Failed to parse updated_parsed: {e}")

    return None


def is_within_freshness_window(
    published: Optional[datetime], freshness_hours: int
) -> bool:
    """
    Check if article was published within the configured freshness window.

    Args:
        published: Article publication datetime (timezone-aware).
        freshness_hours: Number of hours to look back.

    Returns:
        True if within window or if date is unknown (inclusive).
    """
    if published is None:
        # Include articles with unknown dates to avoid missing content
        return True

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=freshness_hours)
    return published >= cutoff


def fetch_rss_feed(
    feed_url: str,
    topic: str,
    max_articles: int = 50,
    freshness_hours: int = 24,
) -> list[Article]:
    """
    Fetch and parse articles from a single RSS feed.

    Args:
        feed_url: URL of the RSS feed.
        topic: Topic category for these articles.
        max_articles: Maximum number of articles to return.
        freshness_hours: Only include articles from last N hours.

    Returns:
        List of Article objects from this feed.
    """
    logger.info(f"Fetching feed: {feed_url}")

    try:
        # feedparser handles most RSS/Atom formats
        feed = feedparser.parse(feed_url)

        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Feed parse warning for {feed_url}: {feed.bozo_exception}")

        articles = []
        source_name = feed.feed.get("title", feed_url)

        for entry in feed.entries[:max_articles]:
            published = parse_published_date(entry)

            # Filter by freshness window from config
            if not is_within_freshness_window(published, freshness_hours):
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

        logger.info(
            f"Fetched {len(articles)} articles from {source_name} "
            f"(last {freshness_hours}h)"
        )
        return articles

    except Exception as e:
        logger.error(f"Failed to fetch feed {feed_url}: {e}")
        return []


def fetch_all_feeds() -> list[Article]:
    """
    Fetch articles from all RSS feeds in config/sources.yaml.

    Reads settings (freshness_hours, max_articles_per_feed) from config.

    Returns:
        Combined list of Article objects from all feeds.
    """
    config = load_sources_config()
    rss_feeds = config.get("rss_feeds", {})

    # Read settings from config with defaults
    settings = config.get("settings", {})
    freshness_hours = settings.get("freshness_hours", 24)
    max_articles_per_feed = settings.get("max_articles_per_feed", 50)

    logger.info(
        f"Aggregator settings: freshness={freshness_hours}h, "
        f"max_per_feed={max_articles_per_feed}"
    )

    all_articles = []

    for topic, feed_urls in rss_feeds.items():
        logger.info(f"Processing topic: {topic} ({len(feed_urls)} feeds)")

        for feed_url in feed_urls:
            articles = fetch_rss_feed(
                feed_url, topic, max_articles_per_feed, freshness_hours
            )
            all_articles.extend(articles)

    logger.info(f"Total articles fetched: {len(all_articles)}")
    return all_articles


def main():
    """CLI entry point for testing the aggregator."""
    import argparse

    parser = argparse.ArgumentParser(description="Fetch news from RSS feeds")
    parser.add_argument(
        "--topic",
        type=str,
        help="Fetch only from specific topic (e.g., 'ai', 'software')",
    )
    args = parser.parse_args()

    config = load_sources_config()
    settings = config.get("settings", {})
    freshness_hours = settings.get("freshness_hours", 24)
    max_articles = settings.get("max_articles_per_feed", 50)

    if args.topic:
        feeds = config.get("rss_feeds", {}).get(args.topic, [])
        if not feeds:
            print(f"No feeds found for topic: {args.topic}")
            return
        articles = []
        for feed_url in feeds:
            articles.extend(
                fetch_rss_feed(feed_url, args.topic, max_articles, freshness_hours)
            )
    else:
        articles = fetch_all_feeds()

    print(f"\n{'='*60}")
    print(f"FETCHED {len(articles)} ARTICLES (last {freshness_hours} hours)")
    print(f"{'='*60}\n")

    display_limit = 20
    for i, article in enumerate(articles[:display_limit], 1):
        pub_str = (
            article.published.strftime("%Y-%m-%d %H:%M")
            if article.published
            else "Unknown"
        )
        title_display = (
            article.title[:60] + "..." if len(article.title) > 60 else article.title
        )
        print(f"{i}. [{article.topic.upper()}] {title_display}")
        print(f"   Source: {article.source} | Published: {pub_str}")
        print(f"   Link: {article.link[:80]}")
        print()

    if len(articles) > display_limit:
        print(f"... and {len(articles) - display_limit} more articles")


if __name__ == "__main__":
    main()
