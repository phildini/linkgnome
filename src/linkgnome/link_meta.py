"""Link metadata fetching and caching."""

from __future__ import annotations

import asyncio
import re

import httpx

from linkgnome.db import LinkgnomeDB


async def fetch_all_titles(
    urls: list[str],
    db: LinkgnomeDB,
    timeout: float = 5.0,
    max_concurrent: int = 8,
) -> dict[str, str | None]:
    """Fetch titles for all URLs in parallel with concurrency control.

    Returns dict mapping original URL -> title (None for broken/failed URLs).
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_one(url: str) -> tuple[str, str | None]:
        async with semaphore:
            cached = db.get_url_metadata(url)
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

                    fetch_url = url
                    if response.status_code in (301, 302, 303, 307, 308):
                        new_url = response.headers.get("location")
                        if new_url:
                            fetch_url = new_url
                    else:
                        content_type = response.headers.get("content-type", "")
                        if "text/html" not in content_type:
                            db.save_url_metadata(url, url, response.status_code)
                            return (fetch_url, url)

                        html = response.text
                        title = _extract_title(html)
                        result = title or url
                        db.save_url_metadata(url, result, response.status_code)
                        return (fetch_url, result)

            except Exception:
                db.save_url_metadata(url, None, 0)
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
