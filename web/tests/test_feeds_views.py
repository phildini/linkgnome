"""Tests for feeds views (dashboard, refresh, polling)."""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from feeds.models import ScoredLink, FeedFetchJob


class DashboardTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dash_user", email="d@b.com", password="x",
        )
        self.user.email_verified = True
        self.user.save()

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("feeds:dashboard"))
        assert response.status_code == 302

    def test_dashboard_shows_empty_state(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("feeds:dashboard"))
        assert response.status_code == 200
        assert b"No links yet" in response.content

    def test_dashboard_shows_links(self):
        self.client.force_login(self.user)
        ScoredLink.objects.create(
            user=self.user, url="https://example.com/a", score=10.0,
            platform="mastodon", title="Test Link",
        )
        response = self.client.get(reverse("feeds:dashboard"))
        assert response.status_code == 200
        assert b"Test Link" in response.content
        assert b"10" in response.content

    def test_dashboard_shows_refresh_button(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("feeds:dashboard"))
        assert b"Refresh" in response.content

    def test_dashboard_shows_connect_prompt(self):
        user = User.objects.create_user(username="newb", email="n@b.com", password="x")
        user.email_verified = True
        user.save()
        self.client.force_login(user)
        response = self.client.get(reverse("feeds:dashboard"))
        assert b"Connect a Mastodon" in response.content

    def test_dashboard_pagination(self):
        self.client.force_login(self.user)
        for i in range(30):
            ScoredLink.objects.create(
                user=self.user, url=f"https://example.com/{i}",
                score=float(i), platform="mastodon",
            )
        response = self.client.get(reverse("feeds:dashboard"))
        assert response.status_code == 200
        response_page2 = self.client.get(reverse("feeds:feed_table") + "?page=2")
        assert response_page2.status_code == 200


class RefreshTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="refresh_user", email="r@b.com", password="x",
        )
        self.user.email_verified = True
        self.user.save()

    def test_refresh_requires_login(self):
        response = self.client.post(reverse("feeds:refresh_feeds"))
        assert response.status_code == 302

    def test_refresh_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("feeds:refresh_feeds"))
        assert response.status_code == 405

    def test_refresh_shows_cooldown(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("feeds:refresh_feeds"))
        assert response.status_code == 200
        assert b"Refresh" in response.content

    def test_refresh_cooldown_blocks(self):
        self.client.force_login(self.user)
        self.user.last_refresh_at = timezone.now()
        self.user.save()
        response = self.client.post(reverse("feeds:refresh_feeds"))
        assert response.status_code == 200
        assert b"300" in response.content or b"299" in response.content


class FeedTableTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="table_user", email="t@b.com", password="x",
        )

    def test_empty_table(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("feeds:feed_table"))
        assert response.status_code == 200
        assert b"No links yet" in response.content

    def test_table_with_links(self):
        self.client.force_login(self.user)
        ScoredLink.objects.create(
            user=self.user, url="https://ex.com", score=5.0, platform="m",
        )
        response = self.client.get(reverse("feeds:feed_table"))
        assert response.status_code == 200
        assert b"ex.com" in response.content
