"""Tests for time range and plan gating in feeds views."""
from datetime import datetime, timedelta, timezone

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from feeds.models import ScoredLink
from feeds.views import _effective_time_range, _filter_links
from links.models import Follow, Identity, Link as PersistentLink


class EffectiveTimeRangeTest(TestCase):
    def test_free_user_defaults_to_24h(self):
        user = User.objects.create_user(username="f", email="f@b.com", password="x")
        assert _effective_time_range(user, "24h") == "24h"

    def test_free_user_cannot_access_7d(self):
        user = User.objects.create_user(username="f", email="f@b.com", password="x")
        assert _effective_time_range(user, "7d") == "24h"

    def test_free_user_cannot_access_30d(self):
        user = User.objects.create_user(username="f", email="f@b.com", password="x")
        assert _effective_time_range(user, "30d") == "24h"

    def test_free_user_cannot_access_all(self):
        user = User.objects.create_user(username="f", email="f@b.com", password="x")
        assert _effective_time_range(user, "all") == "24h"

    def test_gnome_user_can_access_24h(self):
        user = User.objects.create_user(username="g", email="g@b.com", password="x", plan="gnome")
        assert _effective_time_range(user, "24h") == "24h"

    def test_gnome_user_can_access_7d(self):
        user = User.objects.create_user(username="g", email="g@b.com", password="x", plan="gnome")
        assert _effective_time_range(user, "7d") == "7d"

    def test_gnome_user_cannot_access_30d(self):
        user = User.objects.create_user(username="g", email="g@b.com", password="x", plan="gnome")
        assert _effective_time_range(user, "30d") == "24h"

    def test_wizard_user_can_access_all(self):
        user = User.objects.create_user(username="w", email="w@b.com", password="x", plan="wizard")
        assert _effective_time_range(user, "all") == "all"

    def test_wizard_user_can_access_30d(self):
        user = User.objects.create_user(username="w", email="w@b.com", password="x", plan="wizard")
        assert _effective_time_range(user, "30d") == "30d"


class FilterLinksPlanTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="t", email="a@b.com", password="x",
        )
        self.identity = Identity.objects.create(
            platform="mastodon", username="author", platform_user_id="1",
        )
        Follow.objects.create(user=self.user, identity=self.identity)
        self.link = PersistentLink.objects.create(
            url="https://ex.com/a", canonical_url="https://ex.com/a",
            posted_by=self.identity,
            posted_at=datetime.now(timezone.utc) - timedelta(hours=2),
            platform_post_id="p1", score=10.0,
        )

    def test_24h_uses_scoredlink(self):
        ScoredLink.objects.create(
            user=self.user, url="https://ex.com/s", score=5.0, platform="mastodon",
        )
        results = _filter_links(self.user, "all", "24h")
        assert len(results) == 1
        assert results[0].score == 5.0

    def test_7d_uses_persistentlink(self):
        results = _filter_links(self.user, "all", "7d")
        assert len(results) == 1
        assert results[0].score == 10.0

    def test_7d_filters_by_platform(self):
        bluesky_identity = Identity.objects.create(
            platform="bluesky", username="bsky_user", platform_user_id="2",
        )
        Follow.objects.create(user=self.user, identity=bluesky_identity)
        PersistentLink.objects.create(
            url="https://ex.com/b", canonical_url="https://ex.com/b",
            posted_by=bluesky_identity,
            posted_at=datetime.now(timezone.utc) - timedelta(hours=1),
            platform_post_id="p2", score=5.0,
        )
        results = _filter_links(self.user, "bluesky", "7d")
        assert len(results) == 1
        assert results[0].url == "https://ex.com/b"

    def test_7d_excludes_unfollowed(self):
        other = User.objects.create_user(username="o", email="o@b.com", password="x")
        ScoredLink.objects.create(user=other, url="https://ex.com/o", score=1.0, platform="m")
        results = _filter_links(other, "all", "7d")
        assert len(results) == 0

    def test_7d_respects_cutoff(self):
        PersistentLink.objects.create(
            url="https://ex.com/old", canonical_url="https://ex.com/old",
            posted_by=self.identity,
            posted_at=datetime.now(timezone.utc) - timedelta(days=30),
            platform_post_id="p_old", score=1.0,
        )
        results = _filter_links(self.user, "all", "7d")
        assert len(results) == 1
        assert results[0].url == "https://ex.com/a"

    def test_all_shows_everything(self):
        PersistentLink.objects.create(
            url="https://ex.com/old", canonical_url="https://ex.com/old",
            posted_by=self.identity,
            posted_at=datetime.now(timezone.utc) - timedelta(days=30),
            platform_post_id="p_old", score=1.0,
        )
        results = _filter_links(self.user, "all", "all")
        assert len(results) == 2


class PersistentLinkTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="t", email="a@b.com", password="x",
        )
        self.user.plan = "gnome"
        self.user.save()
        self.identity = Identity.objects.create(
            platform="mastodon", username="author", platform_user_id="1",
        )
        Follow.objects.create(user=self.user, identity=self.identity)
        PersistentLink.objects.create(
            url="https://ex.com/a", canonical_url="https://ex.com/a",
            posted_by=self.identity,
            posted_at=datetime.now(timezone.utc) - timedelta(hours=2),
            platform_post_id="p1", score=10.0,
        )

    def test_dashboard_shows_persistent_links_for_7d(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("feeds:dashboard") + "?range=7d")
        assert response.status_code == 200
        assert b"ex.com" in response.content
