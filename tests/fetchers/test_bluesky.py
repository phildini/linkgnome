"""Tests for Bluesky fetcher."""

from __future__ import annotations

import pytest
import respx
import httpx

from linkgnome.fetchers.base import Platform, TimelineType
from linkgnome.fetchers.bluesky import BlueskyFetcher


SAMPLE_BLUESKY_FEED = {
    "feed": [
        {
            "post": {
                "uri": "at://did:plc:abc/app.bsky.feed.post/xyz123",
                "record": {
                    "text": "Check out https://example.com/article for more info",
                    "createdAt": "2024-01-15T10:30:00.000Z",
                    "facets": [],
                },
                "author": {
                    "handle": "testuser.bsky.social",
                    "displayName": "Test User",
                },
                "repostCount": 5,
                "likeCount": 12,
                "embed": {},
            },
        },
        {
            "post": {
                "uri": "at://did:plc:def/app.bsky.feed.post/abc789",
                "record": {
                    "text": "Another post with https://other-site.org/link",
                    "createdAt": "2024-01-15T09:00:00.000Z",
                    "facets": [],
                },
                "author": {
                    "handle": "another.bsky.social",
                    "displayName": "Another Person",
                },
                "repostCount": 0,
                "likeCount": 3,
                "embed": {},
            },
        },
    ]
}


class TestBlueskyFetcher:
    """Tests for the BlueskyFetcher class."""

    def test_get_platform(self):
        """Test that get_platform returns BLUESKY."""
        fetcher = BlueskyFetcher("user.bsky.social", "password")
        assert fetcher.get_platform() == Platform.BLUESKY

    def test_extract_urls_from_content(self):
        """Test URL extraction from Bluesky content."""
        fetcher = BlueskyFetcher("user.bsky.social", "password")
        urls = fetcher.extract_urls_from_content(
            "Check out https://example.com/article and http://other-site.org"
        )
        assert "https://example.com/article" in urls
        assert "http://other-site.org" in urls
        assert len(urls) == 2

    def test_parse_feed_item_regular_post(self):
        """Test parsing a regular Bluesky post."""
        fetcher = BlueskyFetcher("user.bsky.social", "password")
        item = SAMPLE_BLUESKY_FEED["feed"][0]

        import asyncio

        post = asyncio.run(fetcher._parse_feed_item(item))

        assert post is not None
        assert post.platform == Platform.BLUESKY
        assert post.author == "testuser.bsky.social"
        assert post.author_display_name == "Test User"
        assert post.is_boost is False
        assert post.boost_count == 5
        assert post.like_count == 12
        assert "https://example.com/article" in post.urls

    def test_parse_feed_item_empty_record(self):
        """Test parsing an item with empty data doesn't crash."""
        fetcher = BlueskyFetcher("user.bsky.social", "password")
        item = {"post": {}}

        import asyncio

        post = asyncio.run(fetcher._parse_feed_item(item))

        assert post is not None
        assert post.author == "unknown"

    def test_parse_feed_item_malformed(self):
        """Test that parsing malformed data returns None."""
        fetcher = BlueskyFetcher("user.bsky.social", "password")

        import asyncio

        post = asyncio.run(fetcher._parse_feed_item("not a dict"))

        assert post is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_timeline_empty(self):
        """Test fetching an empty timeline."""
        respx.get("https://api.bsky.app/xrpc/app.bsky.feed.getTimeline").mock(
            return_value=httpx.Response(200, json={"feed": []})
        )

        fetcher = BlueskyFetcher("user.bsky.social", "password")
        fetcher.access_jwt = "fake-token"

        posts = await fetcher.fetch_timeline(timeline_type=TimelineType.HOME, limit=10)

        assert len(posts) == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_timeline_with_data(self):
        """Test fetching timeline with sample data."""
        respx.get("https://api.bsky.app/xrpc/app.bsky.feed.getTimeline").mock(
            return_value=httpx.Response(200, json=SAMPLE_BLUESKY_FEED)
        )

        fetcher = BlueskyFetcher("user.bsky.social", "password")
        fetcher.access_jwt = "fake-token"

        posts = await fetcher.fetch_timeline(timeline_type=TimelineType.HOME, limit=20)

        assert len(posts) == 2
        assert "https://example.com/article" in posts[0].urls
        assert "https://other-site.org/link" in posts[1].urls

    @pytest.mark.asyncio
    @respx.mock
    async def test_authenticate(self):
        """Test authentication with mock response."""
        respx.post("https://bsky.social/xrpc/com.atproto.server.createSession").mock(
            return_value=httpx.Response(
                200,
                json={
                    "accessJwt": "test-access-jwt",
                    "refreshJwt": "test-refresh-jwt",
                    "did": "did:plc:abc123",
                },
            )
        )

        fetcher = BlueskyFetcher("user.bsky.social", "password")
        result = await fetcher.authenticate()

        assert result["accessJwt"] == "test-access-jwt"
        assert fetcher.access_jwt == "test-access-jwt"
        assert fetcher.refresh_jwt == "test-refresh-jwt"
        assert fetcher.did == "did:plc:abc123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_credentials_no_token_first(self):
        """Test verify_credentials authenticates if no token exists."""
        respx.post("https://bsky.social/xrpc/com.atproto.server.createSession").mock(
            return_value=httpx.Response(
                200,
                json={
                    "accessJwt": "test-access-jwt",
                    "refreshJwt": "test-refresh-jwt",
                    "did": "did:plc:abc123",
                },
            )
        )

        fetcher = BlueskyFetcher("user.bsky.social", "password")
        result = await fetcher.verify_credentials()

        assert result["handle"] == "user.bsky.social"
