"""Bluesky feed fetcher implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from linkgnome.fetchers.base import BaseFetcher, Platform, Post, TimelineType


class BlueskyFetcher(BaseFetcher):
    """Fetcher for Bluesky timeline data."""

    BSKY_API = "https://api.bsky.app"
    BSKY_ATPROTO = "https://bsky.social"

    def __init__(
        self,
        handle: str,
        app_password: str,
    ):
        self.handle = handle
        self.app_password = app_password
        self.access_jwt: str | None = None
        self.refresh_jwt: str | None = None
        self.did: str | None = None

    async def authenticate(self) -> dict[str, str]:
        """Authenticate with Bluesky using handle and app password."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BSKY_ATPROTO}/xrpc/com.atproto.server.createSession",
                json={
                    "identifier": self.handle,
                    "password": self.app_password,
                },
            )
            response.raise_for_status()
            data = response.json()
            self.access_jwt = data.get("accessJwt")
            self.refresh_jwt = data.get("refreshJwt")
            self.did = data.get("did")
            return data

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers, refreshing token if needed."""
        if not self.access_jwt:
            await self.authenticate()
        return {"Authorization": f"Bearer {self.access_jwt}"}

    async def verify_credentials(self) -> dict[str, Any]:
        """Verify Bluesky credentials by authenticating."""
        result = await self.authenticate()
        return {
            "handle": self.handle,
            "did": self.did or result.get("did", ""),
        }

    async def fetch_timeline(
        self,
        timeline_type: TimelineType = TimelineType.HOME,
        max_id: str | None = None,
        limit: int = 40,
        cutoff: datetime | None = None,
    ) -> list[Post]:
        """Fetch posts from the specified timeline."""
        if not self.access_jwt:
            await self.authenticate()

        posts = []
        cursor = max_id
        page_count = 0
        max_pages = 10

        while page_count < max_pages:
            page_count += 1
            async with httpx.AsyncClient(
                base_url=self.BSKY_API,
                timeout=30.0,
            ) as client:
                params: dict[str, Any] = {"limit": limit}
                if cursor:
                    params["cursor"] = cursor

                response = await client.get(
                    "/xrpc/app.bsky.feed.getTimeline",
                    headers=await self._get_auth_headers(),
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            feed = data.get("feed", [])
            if not feed:
                break

            for item in feed:
                post = await self._parse_feed_item(item)
                if post is None:
                    continue
                if cutoff and post.created_at < cutoff:
                    continue
                posts.append(post)

            cursor = data.get("cursor")
            if not cursor:
                break

        return posts

    async def extract_urls_from_post(self, post_data: dict[str, Any]) -> list[str]:
        """Extract URLs from a Bluesky post."""
        record = post_data.get("record", {})
        facets = record.get("facets", [])

        facet_urls = []
        for facet in facets:
            for feature in facet.get("features", []):
                if feature.get("$type") == "app.bsky.richtext.facet#link":
                    uri = feature.get("uri", "")
                    if uri:
                        facet_urls.append(uri)

        if facet_urls:
            return facet_urls

        return self.extract_urls_from_content(record.get("text", ""))

    def get_platform(self) -> Platform:
        """Return the platform this fetcher supports."""
        return Platform.BLUESKY

    async def _parse_feed_item(self, item: dict[str, Any]) -> Post | None:
        """Parse a Bluesky feed item into a Post object."""
        try:
            post_data = item.get("post", {})
            record = post_data.get("record", {})
            author = post_data.get("author", {})

            created_at_str = record.get("createdAt", "")
            if created_at_str:
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
            else:
                created_at = datetime.now(timezone.utc)

            is_boost = (
                item.get("reason", {}).get("$type") == "app.bsky.feed.defs#reasonRepost"
            )
            boost_count = post_data.get("repostCount", 0)
            like_count = post_data.get("likeCount", 0)

            urls = await self.extract_urls_from_post(post_data)

            post = Post(
                id=post_data.get("uri", ""),
                platform=Platform.BLUESKY,
                author=author.get("handle", "unknown"),
                author_display_name=author.get(
                    "displayName", author.get("handle", "unknown")
                ),
                content=record.get("text", ""),
                urls=urls,
                created_at=created_at,
                is_boost=is_boost,
                original_post_id=post_data.get("uri") if not is_boost else None,
                boosted_by=item.get("reason", {}).get("by", {}).get("handle")
                if is_boost
                else None,
                boost_count=boost_count,
                like_count=like_count,
                raw_data=item,
            )
            return post
        except Exception:
            return None
