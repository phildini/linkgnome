"""Background task for fetching and scoring feeds."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from feeds.models import ScoredLink

logger = logging.getLogger(__name__)


def fetch_user_feeds(user_id: int) -> None:
    """Synchronous entry point for feed fetching."""
    logger.info("Fetching feeds for user %s", user_id)
    with asyncio.Runner() as runner:
        runner.run(_fetch_user_feeds_async(user_id))
    logger.info("Feed fetch complete for user %s", user_id)


async def _fetch_user_feeds_async(user_id: int) -> None:
    User = get_user_model()
    user = await User.objects.aget(id=user_id)
    logger.info("Fetching feeds for %s", user.username)

    posts = []
    from linkgnome.db import LinkgnomeDB

    cache_db = LinkgnomeDB(db_path=Path(settings.LINKGNOME_CACHE_PATH))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    mastodon = getattr(user, "mastodon_account", None)
    if mastodon and mastodon.is_active:
        try:
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
        except Exception as e:
            logger.exception("Mastodon fetch failed for %s", user.username)

    bluesky = getattr(user, "bluesky_account", None)
    if bluesky and bluesky.is_active:
        try:
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
        except Exception as e:
            logger.exception("Bluesky fetch failed for %s", user.username)

    from linkgnome.scorer import score_links

    scored = await score_links(posts, db=cache_db)
    logger.info("Scored %d links", len(scored))

    await _store_scored_links(user, scored)


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
    logger.info("Stored %d scored links for %s", len(scored_links), user.username)
