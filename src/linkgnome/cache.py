"""Caching layer for fetched feed data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from diskcache import Cache


class FeedCache:
    """Cache for feed data."""

    def __init__(self, cache_dir: Path | None = None, ttl_seconds: int = 600):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "linkgnome"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self._cache = Cache(str(self.cache_dir))

    def get_feed(
        self, platform: str, timeline_type: str
    ) -> list[dict[str, Any]] | None:
        """Get cached feed data if it hasn't expired."""
        cache_key = f"{platform}:{timeline_type}"
        cached = self._cache.get(cache_key)
        if cached is None:
            return None

        data, timestamp = cached
        if datetime.now().timestamp() - timestamp > self.ttl_seconds:
            self._cache.delete(cache_key)
            return None

        return data

    def set_feed(
        self,
        platform: str,
        timeline_type: str,
        posts: list[dict[str, Any]],
    ) -> None:
        """Cache feed data."""
        cache_key = f"{platform}:{timeline_type}"
        self._cache.set(
            cache_key,
            (posts, datetime.now().timestamp()),
            expire=self.ttl_seconds,
        )

    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()

    def close(self) -> None:
        """Close the cache."""
        self._cache.close()
