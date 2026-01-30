"""
Shared data models for the news aggregation agent.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    """
    Standardized article representation.

    Used across all components: MCP server, LangGraph agent, formatter.
    """

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

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        """Create Article from dictionary."""
        published = None
        if data.get("published"):
            try:
                published = datetime.fromisoformat(data["published"])
            except (ValueError, TypeError):
                pass

        return cls(
            title=data.get("title", ""),
            link=data.get("link", ""),
            summary=data.get("summary", ""),
            source=data.get("source", ""),
            topic=data.get("topic", ""),
            published=published,
            score=data.get("score", 0.0),
            ai_summary=data.get("ai_summary", ""),
        )
