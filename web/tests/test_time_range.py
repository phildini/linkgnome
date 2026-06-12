"""Tests for time range and plan gating in feeds views."""
from datetime import datetime, timedelta, timezone

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from feeds.models import ScoredLink
from feeds.views import _effective_time_range, _filter_links


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

    def test_24h_includes_recently_seen(self):
        ScoredLink.objects.create(
            user=self.user, url="https://ex.com/a", score=10.0,
            platform="mastodon",
        )
        results = _filter_links(self.user, "all", "24h")
        assert len(results) == 1

    def test_24h_excludes_old_links(self):
        link = ScoredLink.objects.create(
            user=self.user, url="https://ex.com/old", score=1.0,
            platform="mastodon",
        )
        ScoredLink.objects.filter(pk=link.pk).update(
            last_seen_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        results = _filter_links(self.user, "all", "24h")
        assert len(results) == 0

    def test_24h_filters_by_platform(self):
        ScoredLink.objects.create(
            user=self.user, url="https://ex.com/a", score=10.0,
            platform="mastodon",
        )
        ScoredLink.objects.create(
            user=self.user, url="https://ex.com/b", score=5.0,
            platform="bluesky",
        )
        results = _filter_links(self.user, "mastodon", "24h")
        assert len(results) == 1
        assert results[0].url == "https://ex.com/a"

    def test_7d_includes_recent_links(self):
        ScoredLink.objects.create(
            user=self.user, url="https://ex.com/a", score=10.0,
            platform="mastodon",
        )
        results = _filter_links(self.user, "all", "7d")
        assert len(results) == 1
        assert results[0].score == 10.0

    def test_7d_excludes_old_links(self):
        link = ScoredLink.objects.create(
            user=self.user, url="https://ex.com/old", score=1.0,
            platform="mastodon",
        )
        ScoredLink.objects.filter(pk=link.pk).update(
            first_seen_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        link2 = ScoredLink.objects.create(
            user=self.user, url="https://ex.com/a", score=10.0,
            platform="mastodon",
        )
        results = _filter_links(self.user, "all", "7d")
        assert len(results) == 1
        assert results[0].url == "https://ex.com/a"

    def test_all_shows_everything(self):
        ScoredLink.objects.create(
            user=self.user, url="https://ex.com/a", score=10.0,
            platform="mastodon",
        )
        ScoredLink.objects.create(
            user=self.user, url="https://ex.com/b", score=5.0,
            platform="bluesky",
        )
        results = _filter_links(self.user, "all", "all")
        assert len(results) == 2


class DashboardRangeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="t", email="a@b.com", password="x",
        )
        self.user.plan = "gnome"
        self.user.save()

    def test_dashboard_shows_links_for_7d(self):
        ScoredLink.objects.create(
            user=self.user, url="https://ex.com/a", score=10.0,
            platform="mastodon",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("feeds:dashboard") + "?range=7d")
        assert response.status_code == 200
        assert b"ex.com" in response.content
