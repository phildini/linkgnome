"""Background task for fetching and scoring feeds."""
import asyncio
import html as html_mod
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from feeds.models import FeedFetchJob, ScoredLink

logger = logging.getLogger(__name__)


def fetch_user_feeds(user_id: int) -> None:
    """Task entry point for django-q2 worker."""
    asyncio.run(_fetch_user_feeds_async(user_id))


async def _fetch_user_feeds_async(user_id: int) -> None:
    User = get_user_model()
    user = await User.objects.aget(id=user_id)

    job = await FeedFetchJob.objects.acreate(user=user, status="running")
    job.started_at = datetime.now(timezone.utc)

    try:
        posts = []
        from linkgnome.db import LinkgnomeDB

        cache_db = LinkgnomeDB(db_path=Path(settings.LINKGNOME_CACHE_PATH))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        mastodon_accounts = await sync_to_async(list)(
            user.mastodon_accounts.filter(is_active=True)
        )
        for acct in mastodon_accounts:
            from linkgnome.fetchers.mastodon import MastodonFetcher
            token = acct.access_token
            logger.info("Mastodon %s: token length %s", acct.instance_url, len(token) if token else 0)
            fetcher = MastodonFetcher(
                instance_url=acct.instance_url,
                access_token=token,
            )
            m_posts = await fetcher.fetch_timeline(cutoff=cutoff)
            logger.info("Mastodon %s: %d posts", acct.instance_url, len(m_posts))
            posts.extend(m_posts)

        bluesky_accounts = await sync_to_async(list)(
            user.bluesky_accounts.filter(is_active=True)
        )
        for acct in bluesky_accounts:
            from linkgnome.fetchers.bluesky import BlueskyFetcher
            pw = acct.app_password
            logger.info("Bluesky %s: password length %s", acct.handle, len(pw) if pw else 0)
            fetcher = BlueskyFetcher(
                handle=acct.handle,
                app_password=pw,
            )
            b_posts = await fetcher.fetch_timeline(cutoff=cutoff)
            logger.info("Bluesky %s: %d posts", acct.handle, len(b_posts))
            posts.extend(b_posts)

        from linkgnome.scorer import score_links

        scored = await score_links(posts, db=cache_db)
        logger.info("Scored %d links", len(scored))

        await _fill_missing_titles(scored, cache_db)
        logger.info("Filled missing titles")

        await _store_scored_links(user, scored)

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        await job.asave()

    except Exception as exc:
        logger.exception("Feed fetch failed for user %s", user_id)
        job.status = "failed"
        job.error_message = str(exc)
        await job.asave()


async def _store_scored_links(user, scored_links) -> None:
    """Bulk replace scored links for a user."""
    await sync_to_async(_store_scored_links_sync)(user, scored_links)


def _extract_post_url(post) -> str:
    """Extract the original post URL from a Post object."""
    if post.raw_data:
        if post.platform.value == "mastodon":
            return post.raw_data.get("url") or post.raw_data.get("uri") or ""
        if post.platform.value == "bluesky":
            post_data = post.raw_data.get("post", {})
            uri = post_data.get("uri", "")
            author = post_data.get("author", {})
            handle = author.get("handle", "")
            if handle and uri:
                parts = uri.split("/")
                rkey = parts[-1] if parts else ""
                return f"https://bsky.app/profile/{handle}/post/{rkey}"
            return uri
    return post.id


def _store_scored_links_sync(user, scored_links) -> None:
    """Synchronous version of _store_scored_links."""
    with transaction.atomic():
        ScoredLink.objects.filter(user=user).delete()
        ScoredLink.objects.bulk_create([
            ScoredLink(
                user=user,
                url=link.url,
                title=link.title,
                score=link.score,
                platform="+".join(
                    sorted(p.value for p in (link.source_platforms or []))
                ),
                author_names=", ".join(
                    set(
                        p.author_display_name or p.author
                        for p in (link.posts or [])
                    )
                ),
                author_post_urls=[_extract_post_url(p) for p in (link.posts or []) if p],
                last_posted_at=max(
                    (p.created_at for p in (link.posts or []) if p and p.created_at),
                    default=None,
                ),
                post_count=link.post_count,
                boost_count=link.boost_count,
                like_count=link.like_count,
            )
            for link in scored_links
        ])
    logger.info("Stored %d scored links for %s", len(scored_links), user.username)


async def _fetch_title_robust(url: str) -> str | None:
    """Fetch a page title with og:title/twitter:title fallback."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LinkGnome/1.0)"}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, max_redirects=5) as client:
            response = await client.get(url, headers=headers)
            if "text/html" not in response.headers.get("content-type", ""):
                return None

            html = response.text

            m = re.search(r'<meta\s+property=[\'"]og:title[\'"]\s+content=[\'"](.*?)[\'"]\s*/?>', html, re.IGNORECASE)
            if m:
                return html_mod.unescape(m.group(1).strip())

            m = re.search(r'<meta\s+name=[\'"]twitter:title[\'"]\s+content=[\'"](.*?)[\'"]\s*/?>', html, re.IGNORECASE)
            if m:
                return html_mod.unescape(m.group(1).strip())

            m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            if m:
                title = m.group(1).strip()
                return html_mod.unescape(title) if title else None

            return None
    except Exception:
        return None


async def _fill_missing_titles(scored_links: list, cache_db) -> None:
    """Re-fetch titles for links that got URL as title (no real title found)."""
    missing = [link for link in scored_links if link.title == link.url]
    if not missing:
        logger.info("All %d links have real titles", len(scored_links))
        return

    logger.info("Fetching missing titles for %d/%d links", len(missing), len(scored_links))

    for link in missing:
        title = await _fetch_title_robust(link.url)
        if title:
            link.title = title
            cache_db.save_url_metadata(link.url, title, 200)

    filled = sum(1 for link in missing if link.title != link.url)
    logger.info("Filled %d/%d missing titles", filled, len(missing))
