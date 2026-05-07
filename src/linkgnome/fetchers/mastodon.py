"""Mastodon feed fetcher implementation."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from linkgnome.fetchers.base import BaseFetcher, Platform, Post, TimelineType

BATCH_SIZE = 40
MAX_PAGES = 10


class MastodonFetcher(BaseFetcher):
    """Fetcher for Mastodon timeline data."""

    def __init__(
        self,
        instance_url: str,
        access_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        if instance_url.startswith("http"):
            self.instance_url = instance_url
        else:
            self.instance_url = f"https://{instance_url}"

        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create an async HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=self.instance_url,
                timeout=30.0,
                http2=True,
            )
        return self.client

    async def register_app(self) -> dict[str, str]:
        """Register an OAuth application with the Mastodon instance."""
        client = await self._get_client()
        response = await client.post(
            "/api/v1/apps",
            data={
                "client_name": "LinkGnome",
                "redirect_uris": "urn:ietf:wg:oauth:2.0:oob",
                "scopes": "read:statuses read:notifications",
                "website": "https://github.com/phildini/linkgnome",
            },
        )
        response.raise_for_status()
        return response.json()

    def get_auth_url(self, client_id: str, instance_url: str) -> str:
        """Get the authorization URL for OAuth flow."""
        return (
            f"{instance_url}/oauth/authorize?"
            f"client_id={client_id}"
            f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
            f"&response_type=code"
            f"&scope=read:statuses+read:notifications"
            f"&force_login=true"
        )

    async def get_access_token(
        self,
        client_id: str,
        client_secret: str,
        code: str,
        instance_url: str,
    ) -> dict[str, str]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{instance_url}/oauth/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    async def fetch_timeline(
        self,
        timeline_type: TimelineType = TimelineType.HOME,
        max_id: str | None = None,
        limit: int | None = None,
        since_id: str | None = None,
        cutoff: datetime | None = None,
    ) -> list[Post]:
        """Fetch posts from the specified timeline with pagination."""
        client = await self._get_client()
        endpoint = self._get_timeline_endpoint(timeline_type)

        page_limit = limit or BATCH_SIZE

        params: dict[str, Any] = {"limit": page_limit}
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id

        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        all_posts = []

        for _ in range(MAX_PAGES):
            response = await client.get(
                endpoint,
                params=params,
                headers=headers,
            )
            response.raise_for_status()

            posts_data = response.json()
            if not posts_data:
                break

            for post_data in posts_data:
                post = self._parse_post(post_data)
                if post is None:
                    continue
                if cutoff and post.created_at < cutoff:
                    break
                all_posts.append(post)

            if cutoff and all_posts and all_posts[-1].created_at < cutoff:
                break

            next_url = self._parse_next_url(response)
            if not next_url:
                break

            params = {"limit": page_limit}
            parsed = urlparse(next_url)
            query_params = parse_qs(parsed.query)
            if "max_id" in query_params:
                params["max_id"] = query_params["max_id"][0]

        return all_posts

    def _parse_next_url(self, response: httpx.Response) -> str | None:
        """Extract next page URL from Link header."""
        link_header = response.headers.get("Link", "")
        if not link_header:
            return None
        for part in link_header.split(", "):
            if '>; rel="next"' in part:
                match = re.match(r"<([^>]+)>", part)
                if match:
                    return match.group(1)
        return None

    async def verify_credentials(self) -> dict[str, Any]:
        """Verify Mastodon credentials by fetching account info."""
        if not self.access_token:
            raise ValueError("No access token provided")

        client = await self._get_client()
        response = await client.get(
            "/api/v1/accounts/verify_credentials",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        response.raise_for_status()
        return response.json()

    def get_platform(self) -> Platform:
        """Return the platform this fetcher supports."""
        return Platform.MASTODON

    def _get_timeline_endpoint(self, timeline_type: TimelineType) -> str:
        """Get the API endpoint for a given timeline type."""
        endpoints = {
            TimelineType.HOME: "/api/v1/timelines/home",
            TimelineType.LOCAL: "/api/v1/timelines/public",
            TimelineType.PUBLIC: "/api/v1/timelines/public",
        }
        endpoint = endpoints.get(timeline_type, endpoints[TimelineType.HOME])
        return endpoint

    def _parse_post(self, data: dict[str, Any]) -> Post | None:
        """Parse a Mastodon status into a Post object."""
        try:
            is_boost = data.get("reblog") is not None
            original_data = data.get("reblog") if is_boost else data
            original_post_id = (
                data.get("reblog", {}).get("id") if is_boost else data.get("id")
            )

            author_data = data.get("account", {})
            if is_boost:
                original_author = data.get("reblog", {}).get("account", {})
                author = original_author.get("username", "unknown")
                display_name = original_author.get("display_name", author)
                boosted_by = author_data.get("username", "unknown")
            else:
                author = author_data.get("username", "unknown")
                display_name = author_data.get("display_name", author)
                boosted_by = None

            content_html = original_data.get("content", "")
            urls = self._extract_urls_from_status(original_data)

            created_at_str = original_data.get("created_at", "")
            created_at = (
                datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                if created_at_str
                else datetime.now(timezone.utc)
            )

            boosts = original_data.get("reblogs_count", 0)
            likes = original_data.get("favourites_count", 0)

            post = Post(
                id=str(data.get("id", "")),
                platform=Platform.MASTODON,
                author=author,
                author_display_name=display_name,
                content=content_html,
                urls=urls,
                created_at=created_at,
                is_boost=is_boost,
                original_post_id=str(original_post_id) if original_post_id else None,
                boosted_by=boosted_by,
                boost_count=boosts,
                like_count=likes,
                raw_data=data,
            )
            return post
        except Exception:
            return None

    def _extract_urls_from_status(self, data: dict[str, Any]) -> list[str]:
        """Extract all URLs from a Mastodon status."""
        urls = []

        urls.extend(self.extract_urls_from_content(data.get("content", "")))

        media_attachments = data.get("media_attachments", [])
        for attachment in media_attachments:
            remote_url = attachment.get("remote_url") or attachment.get("url")
            if remote_url:
                urls.append(remote_url)

        card = data.get("card", {})
        if card and card.get("url"):
            urls.append(card["url"])

        return list(set(urls))
