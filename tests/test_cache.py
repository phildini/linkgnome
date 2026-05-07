"""Tests for the caching layer."""

import tempfile
from pathlib import Path
from linkgnome.cache import FeedCache


class TestFeedCache:
    """Tests for the FeedCache class."""

    def test_set_and_get_feed(self):
        """Test caching and retrieving feed data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FeedCache(
                cache_dir=Path(tmpdir),
                ttl_seconds=600,
            )

            feed_data = [
                {"id": "1", "author": "user1", "urls": ["https://example.com"]},
            ]

            cache.set_feed("mastodon", "home", feed_data)
            result = cache.get_feed("mastodon", "home")

            assert result is not None
            assert len(result) == 1
            assert result[0]["id"] == "1"

    def test_cache_miss(self):
        """Test that missing cache returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FeedCache(
                cache_dir=Path(tmpdir),
                ttl_seconds=600,
            )

            result = cache.get_feed("nonexistent", "home")
            assert result is None

    def test_cache_expiration(self):
        """Test that expired cache entries return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FeedCache(
                cache_dir=Path(tmpdir),
                ttl_seconds=0,
            )

            feed_data = [{"id": "1"}]
            cache.set_feed("mastodon", "home", feed_data)

            result = cache.get_feed("mastodon", "home")
            assert result is None

    def test_cache_clear(self):
        """Test clearing the cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FeedCache(
                cache_dir=Path(tmpdir),
                ttl_seconds=600,
            )

            cache.set_feed("mastodon", "home", [{"id": "1"}])
            cache.clear()

            result = cache.get_feed("mastodon", "home")
            assert result is None

    def test_different_platforms_isolated(self):
        """Test that different platforms don't interfere."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FeedCache(
                cache_dir=Path(tmpdir),
                ttl_seconds=600,
            )

            cache.set_feed("mastodon", "home", [{"id": "1", "platform": "mastodon"}])
            cache.set_feed("bluesky", "home", [{"id": "2", "platform": "bluesky"}])

            mastodon = cache.get_feed("mastodon", "home")
            bluesky = cache.get_feed("bluesky", "home")

            assert mastodon is not None and mastodon[0]["platform"] == "mastodon"
            assert bluesky is not None and bluesky[0]["platform"] == "bluesky"

    def test_close_cache(self):
        """Test closing the cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FeedCache(
                cache_dir=Path(tmpdir),
                ttl_seconds=600,
            )
            cache.close()
