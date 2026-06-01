"""Background task for fetching and scoring feeds."""
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from feeds.models import ScoredLink, FeedFetchJob


def fetch_user_feeds(user_id: int) -> None:
    """Synchronous entry point for django-q2."""
    with asyncio.Runner() as runner:
        runner.run(_fetch_user_feeds_async(user_id))


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

        mastodon = getattr(user, "mastodon_account", None)
        if mastodon and mastodon.is_active:
            from linkgnome.fetchers.mastodon import MastodonFetcher

            fetcher = MastodonFetcher(
                instance_url=mastodon.instance_url,
                access_token=mastodon.access_token,
            )
            m_posts = await fetcher.fetch_timeline(cutoff=cutoff)
            posts.extend(m_posts)

        bluesky = getattr(user, "bluesky_account", None)
        if bluesky and bluesky.is_active:
            from linkgnome.fetchers.bluesky import BlueskyFetcher

            fetcher = BlueskyFetcher(
                handle=bluesky.handle,
                app_password=bluesky.app_password,
            )
            b_posts = await fetcher.fetch_timeline(cutoff=cutoff)
            posts.extend(b_posts)

        from linkgnome.scorer import score_links

        scored = await score_links(posts, db=cache_db)

        await _store_scored_links(user, scored)

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        await job.asave()

    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        await job.asave()


async def _store_scored_links(user, scored_links) -> None:
    """Bulk replace scored links for a user."""
    from feeds.models import ScoredLink

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
