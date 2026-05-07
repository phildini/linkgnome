"""Tests for Mastodon fetcher."""

from __future__ import annotations

import pytest
import respx
import httpx

from linkgnome.fetchers.base import Platform, TimelineType
from linkgnome.fetchers.mastodon import MastodonFetcher


SAMPLE_STATUS = {
    "id": "123456",
    "account": {
        "username": "testuser",
        "display_name": "Test User",
    },
    "content": "Check out https://example.com/article for more info",
    "created_at": "2024-01-15T10:30:00.000Z",
    "reblog": None,
    "reblogs_count": 5,
    "favourites_count": 12,
    "media_attachments": [],
    "card": {"url": "https://example.com/card"},
}

SAMPLE_REBLOG = {
    "id": "789012",
    "account": {
        "username": "reposter",
        "display_name": "Reposter",
    },
    "content": "",
    "created_at": "2024-01-15T11:00:00.000Z",
    "reblog": SAMPLE_STATUS,
    "reblogs_count": 0,
    "favourites_count": 0,
    "media_attachments": [],
    "card": None,
}


class TestMastodonFetcher:
    """Tests for the MastodonFetcher class."""

    def test_init_with_http_prefix(self):
        """Test that instance URL gets https:// prefix if missing."""
        fetcher = MastodonFetcher("mastodon.social")
        assert fetcher.instance_url == "https://mastodon.social"

    def test_init_keeps_https(self):
        """Test that existing https:// is preserved."""
        fetcher = MastodonFetcher("https://mastodon.social")
        assert fetcher.instance_url == "https://mastodon.social"

    def test_get_platform(self):
        """Test that get_platform returns MASTODON."""
        fetcher = MastodonFetcher("https://mastodon.social")
        assert fetcher.get_platform() == Platform.MASTODON

    def test_get_auth_url(self):
        """Test that auth URL is correctly constructed."""
        fetcher = MastodonFetcher("https://mastodon.social")
        url = fetcher.get_auth_url(
            client_id="abc123",
            instance_url="https://mastodon.social",
        )
        assert "mastodon.social" in url
        assert "abc123" in url
        assert "response_type=code" in url

    def test_get_timeline_endpoint_home(self):
        """Test that HOME timeline returns correct endpoint."""
        fetcher = MastodonFetcher("https://mastodon.social")
        assert (
            fetcher._get_timeline_endpoint(TimelineType.HOME)
            == "/api/v1/timelines/home"
        )

    def test_get_timeline_endpoint_local(self):
        """Test that LOCAL timeline returns public endpoint."""
        fetcher = MastodonFetcher("https://mastodon.social")
        assert (
            fetcher._get_timeline_endpoint(TimelineType.LOCAL)
            == "/api/v1/timelines/public"
        )

    def test_get_timeline_endpoint_public(self):
        """Test that PUBLIC timeline returns public endpoint."""
        fetcher = MastodonFetcher("https://mastodon.social")
        assert (
            fetcher._get_timeline_endpoint(TimelineType.PUBLIC)
            == "/api/v1/timelines/public"
        )

    def test_extract_urls_from_status(self):
        """Test URL extraction from Mastodon status data."""
        fetcher = MastodonFetcher("https://mastodon.social")
        urls = fetcher._extract_urls_from_status(SAMPLE_STATUS)
        assert "https://example.com/article" in urls
        assert "https://example.com/card" in urls

    def test_extract_urls_from_status_with_media(self):
        """Test URL extraction includes media attachments."""
        fetcher = MastodonFetcher("https://mastodon.social")
        status_with_media = {
            "content": "Check https://example.com",
            "media_attachments": [
                {
                    "remote_url": "https://cdn.example.com/image.png",
                    "url": "https://example.com/image.png",
                },
            ],
            "card": None,
        }
        urls = fetcher._extract_urls_from_status(status_with_media)
        assert "https://cdn.example.com/image.png" in urls

    def test_parse_post_regular(self):
        """Test parsing a regular post."""
        fetcher = MastodonFetcher("https://mastodon.social")
        post = fetcher._parse_post(SAMPLE_STATUS)

        assert post is not None
        assert post.id == "123456"
        assert post.platform == Platform.MASTODON
        assert post.author == "testuser"
        assert post.author_display_name == "Test User"
        assert post.is_boost is False
        assert post.boost_count == 5
        assert post.like_count == 12
        assert len(post.urls) == 2
        assert post.boosted_by is None

    def test_parse_post_reblog(self):
        """Test parsing a reblog/boost post."""
        fetcher = MastodonFetcher("https://mastodon.social")
        post = fetcher._parse_post(SAMPLE_REBLOG)

        assert post is not None
        assert post.id == "789012"
        assert post.is_boost is True
        assert post.author == "testuser"
        assert post.boosted_by == "reposter"
        assert post.original_post_id == "123456"

    def test_parse_post_no_content(self):
        """Test parsing a post with minimal data doesn't crash."""
        fetcher = MastodonFetcher("https://mastodon.social")
        post = fetcher._parse_post({})

        assert post is not None
        assert post.author == "unknown"

    def test_parse_post_malformed(self):
        """Test that parsing malformed data returns None."""
        fetcher = MastodonFetcher("https://mastodon.social")
        post = fetcher._parse_post("not a dict")

        assert post is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_register_app(self):
        """Test app registration returns expected data."""
        respx.post("https://mastodon.social/api/v1/apps").mock(
            return_value=httpx.Response(
                200,
                json={
                    "client_id": "test-client-id",
                    "client_secret": "test-client-secret",
                },
            )
        )

        fetcher = MastodonFetcher("https://mastodon.social")
        result = await fetcher.register_app()

        assert result["client_id"] == "test-client-id"
        assert result["client_secret"] == "test-client-secret"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_access_token(self):
        """Test getting an access token."""
        respx.post("https://mastodon.social/oauth/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token123"},
            )
        )

        fetcher = MastodonFetcher("https://mastodon.social")
        result = await fetcher.get_access_token(
            client_id="abc",
            client_secret="secret",
            code="code123",
            instance_url="https://mastodon.social",
        )

        assert result["access_token"] == "token123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_credentials(self):
        """Test verifying credentials."""
        respx.get("https://mastodon.social/api/v1/accounts/verify_credentials").mock(
            return_value=httpx.Response(
                200,
                json={"username": "testuser"},
            )
        )

        fetcher = MastodonFetcher(
            "https://mastodon.social",
            access_token="token",
        )
        result = await fetcher.verify_credentials()

        assert result["username"] == "testuser"

    def test_verify_credentials_no_token(self):
        """Test that verifying without token raises ValueError."""
        fetcher = MastodonFetcher("https://mastodon.social")
        import asyncio

        with pytest.raises(ValueError, match="No access token"):
            asyncio.run(fetcher.verify_credentials())
