"""Link metadata fetching and caching."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import httpx
from diskcache import Cache


class LinkMetadataCache:
    """Cache for URL metadata (titles, status codes)."""

    def __init__(self, cache_dir: Path | None = None, ttl_seconds: int = 86400):
        self.cache_dir = cache_dir or (
            Path.home() / ".cache" / "linkgnome" / "metadata"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self._cache = Cache(str(self.cache_dir))

    def get(self, url: str) -> dict[str, Any] | None:
        return self._cache.get(url)

    def set(self, url: str, title: str | None, status_code: int) -> None:
        self._cache.set(
            url,
            {"title": title, "status_code": status_code},
            expire=self.ttl_seconds,
        )

    def clear(self) -> None:
        self._cache.clear()

    def close(self) -> None:
        self._cache.close()


async def fetch_all_titles(
    urls: list[str],
    cache: LinkMetadataCache,
    timeout: float = 5.0,
    max_concurrent: int = 8,
) -> dict[str, str | None]:
    """Fetch titles for all URLs in parallel with concurrency control.

    Returns dict mapping original URL -> title (None for broken/failed URLs).
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_one(url: str) -> tuple[str, str | None]:
        async with semaphore:
            cached = cache.get(url)
            if cached is not None:
                if cached["status_code"] >= 400:
                    return (url, None)
                return (url, cached["title"])

            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (compatible; LinkGnome/1.0)"
                }
                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=False,
                ) as client:
                    response = await client.get(url, headers=headers)

                    if response.status_code >= 400:
                        cache.set(url, None, response.status_code)
                        return (url, None)

                    if response.status_code in (301, 302, 303, 307, 308):
                        new_url = response.headers.get("location")
                        if new_url:
                            url = new_url
                    else:
                        content_type = response.headers.get("content-type", "")
                        if "text/html" not in content_type:
                            cache.set(url, url, response.status_code)
                            return (url, url)

                        html = response.text
                        title = _extract_title(html)
                        result = title if title else url
                        cache.set(url, result, response.status_code)
                        return (url, result)

            except Exception:
                cache.set(url, None, 0)
                return (url, None)

    tasks = [fetch_one(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    metadata: dict[str, str | None] = {}
    for result in results:
        if isinstance(result, Exception):
            continue
        if result is None:
            continue
        url, title = result
        metadata[url] = title

    return metadata


def _extract_title(html: str) -> str | None:
    """Extract <title> from HTML, stripping tags and whitespace."""
    match = re.search(
        r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL
    )
    if match:
        title = match.group(1).strip()
        return title if title else None
    return None
