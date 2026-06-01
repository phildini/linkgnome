"""Tests for feed fetching tasks."""
import pytest
import respx
from django.test import TestCase, override_settings

from accounts.models import User, MastodonAccount
from feeds.models import FeedFetchJob, ScoredLink
from feeds.tasks import fetch_user_feeds, _store_scored_links_sync

from linkgnome.fetchers.base import Post, Platform
from linkgnome.scorer import ScoredLink as ScoredLinkType

from datetime import datetime, timezone, timedelta


class StoreScoredLinksTest(TestCase):
    def test_store_empty_list(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        _store_scored_links_sync(user, [])
        assert ScoredLink.objects.filter(user=user).count() == 0

    def test_store_replaces_old(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        ScoredLink.objects.create(
            user=user, url="https://old.com", score=1.0, platform="m",
        )
        scored_link = ScoredLinkType(
            url="https://new.com", canonical_url="https://new.com",
            score=5.0, title="New Link", post_count=1, boost_count=0,
            like_count=0, posts=[], source_platforms={Platform.MASTODON},
        )
        _store_scored_links_sync(user, [scored_link])
        assert ScoredLink.objects.filter(user=user).count() == 1
        assert ScoredLink.objects.filter(user=user).first().url == "https://new.com"

    def test_stores_multiple_links(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        links = []
        for i in range(3):
            link = ScoredLinkType(
                url=f"https://ex.com/{i}", canonical_url=f"https://ex.com/{i}",
                score=float(i), title=f"Link {i}", post_count=1,
                boost_count=0, like_count=0, posts=[],
                source_platforms={Platform.MASTODON},
            )
            links.append(link)
        _store_scored_links_sync(user, links)
        assert ScoredLink.objects.filter(user=user).count() == 3

    def test_stores_author_names(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        post = Post(
            id="1", platform=Platform.MASTODON, author="testuser",
            author_display_name="Test User", content="", urls=[],
            created_at=datetime.now(timezone.utc),
        )
        scored_link = ScoredLinkType(
            url="https://ex.com", canonical_url="https://ex.com",
            score=1.0, post_count=1, boost_count=0, like_count=0,
            posts=[post], source_platforms={Platform.MASTODON},
        )
        _store_scored_links_sync(user, [scored_link])
        stored = ScoredLink.objects.get(user=user)
        assert "Test User" in stored.author_names


@pytest.mark.skip(reason="SQLite + asyncio + Django test DB locking issue")
@override_settings(
    LINKGNOME_CACHE_PATH="/tmp/linkgnome-test-cache/test-cache.db",
)
class FetchUserFeedsTest(TestCase):
    def test_fetch_no_accounts(self):
        user = User.objects.create_user(
            username="acctless", email="a@b.com", password="x",
        )
        fetch_user_feeds(user.id)
        job = FeedFetchJob.objects.filter(user=user).order_by("-requested_at").first()
        assert job.status == "completed"

    @respx.mock
    def test_fetch_mastodon_only(self):
        user = User.objects.create_user(
            username="masto_user", email="m@b.com", password="x",
        )
        MastodonAccount.objects.create(
            user=user, instance_url="https://mastodon.social",
            access_token="test_token", mastodon_user_id="1",
            mastodon_username="masto_user",
        )

        timeline_url = "https://mastodon.social/api/v1/timelines/home"
        respx.get(timeline_url).respond(
            200, json=[{
                "id": "100",
                "created_at": "2026-06-01T00:00:00.000Z",
                "account": {"username": "other", "display_name": "Other", "id": "2"},
                "content": "Check this out: https://example.com/article",
                "reblogs_count": 0, "favourites_count": 0,
                "media_attachments": [], "card": None,
            }]
        )

        fetch_user_feeds(user.id)
        job = FeedFetchJob.objects.filter(user=user).order_by("-requested_at").first()
        assert job.status == "completed", f"Job failed: {job.error_message}"
        assert ScoredLink.objects.filter(user=user).exists()

    @respx.mock
    def test_fetch_mastodon_api_error(self):
        user = User.objects.create_user(
            username="masto_fail", email="f@b.com", password="x",
        )
        MastodonAccount.objects.create(
            user=user, instance_url="https://mastodon.social",
            access_token="bad_token", mastodon_user_id="1",
            mastodon_username="fail_user",
        )
        respx.get("https://mastodon.social/api/v1/timelines/home").respond(500)

        fetch_user_feeds(user.id)
        job = FeedFetchJob.objects.filter(user=user).order_by("-requested_at").first()
        assert job.status == "failed"
