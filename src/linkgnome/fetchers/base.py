"""Abstract base class for feed fetchers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class Platform(Enum):
    MASTODON = "mastodon"
    BLUESKY = "bluesky"


class TimelineType(Enum):
    HOME = "home"
    LOCAL = "local"
    PUBLIC = "federated"


@dataclass
class Post:
    """Represents a social media post."""

    id: str
    platform: Platform
    author: str
    author_display_name: str
    content: str
    urls: list[str]
    created_at: datetime
    is_boost: bool = False
    original_post_id: str | None = None
    boosted_by: str | None = None
    liked: bool = False
    boost_count: int = 0
    like_count: int = 0
    raw_data: dict[str, Any] | None = None


@dataclass
class ScoredLink:
    """A link with its computed score."""

    url: str
    canonical_url: str
    score: float
    post_count: int = 0
    boost_count: int = 0
    like_count: int = 0
    posts: list[Post] | None = None
    source_platforms: set[Platform] | None = None


class BaseFetcher(ABC):
    """Abstract base class for all feed fetchers."""

    @abstractmethod
    async def fetch_timeline(
        self,
        timeline_type: TimelineType = TimelineType.HOME,
        max_id: str | None = None,
        limit: int = 40,
    ) -> list[Post]:
        """Fetch posts from the specified timeline."""
        ...

    @abstractmethod
    async def verify_credentials(self) -> dict[str, Any]:
        """Verify that the credentials are valid."""
        ...

    @abstractmethod
    def get_platform(self) -> Platform:
        """Return the platform this fetcher supports."""
        ...

    @staticmethod
    def extract_urls_from_content(content: str) -> list[str]:
        """Extract URLs from post content."""
        import re

        url_pattern = re.compile(
            r'https?://[^\s<>"]+|www\.[^\s<>"]+',
            re.IGNORECASE,
        )
        urls = url_pattern.findall(content)
        return [url if url.startswith("http") else f"https://{url}" for url in urls]
