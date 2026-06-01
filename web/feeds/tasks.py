"""Background task for fetching and scoring feeds."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

        mastodon = await sync_to_async(getattr)(user, "mastodon_account", None)
        if mastodon and mastodon.is_active:
            from linkgnome.fetchers.mastodon import MastodonFetcher
            token = mastodon.access_token
            logger.info("Mastodon token length: %s", len(token) if token else 0)
            fetcher = MastodonFetcher(
                instance_url=mastodon.instance_url,
                access_token=token,
            )
            m_posts = await fetcher.fetch_timeline(cutoff=cutoff)
            logger.info("Mastodon: %d posts", len(m_posts))
            posts.extend(m_posts)

        bluesky = await sync_to_async(getattr)(user, "bluesky_account", None)
        if bluesky and bluesky.is_active:
            from linkgnome.fetchers.bluesky import BlueskyFetcher
            pw = bluesky.app_password
            logger.info("Bluesky password length: %s", len(pw) if pw else 0)
            fetcher = BlueskyFetcher(
                handle=bluesky.handle,
                app_password=pw,
            )
            b_posts = await fetcher.fetch_timeline(cutoff=cutoff)
            logger.info("Bluesky: %d posts", len(b_posts))
            posts.extend(b_posts)

        from linkgnome.scorer import score_links

        scored = await score_links(posts, db=cache_db)
        logger.info("Scored %d links", len(scored))

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
    async with transaction.atomic():
        await ScoredLink.objects.filter(user=user).adelete()
        await ScoredLink.objects.abulk_create([
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
                post_count=link.post_count,
                boost_count=link.boost_count,
                like_count=link.like_count,
            )
            for link in scored_links
        ])
    username = await sync_to_async(getattr)(user, "username", str(user.id))
    logger.info("Stored %d scored links for %s", len(scored_links), username)
