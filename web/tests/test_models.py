"""Tests for accounts and feeds models."""
from django.test import TestCase

from accounts.models import User, MastodonAccount, BlueskyAccount
from feeds.models import ScoredLink, FeedFetchJob


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="secret"
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.plan == "free"
        assert user.email_verified is False
        assert user.is_fully_activated is False

    def test_fully_activated(self):
        user = User.objects.create_user(username="test", email="a@b.com", password="x")
        user.email_verified = True
        user.save()
        assert user.is_fully_activated is True

    def test_refresh_cooldown(self):
        user = User.objects.create_user(username="test", email="a@b.com", password="x")
        assert user.refresh_cooldown_seconds == 300

    def test_max_mastodon_accounts_free(self):
        user = User.objects.create_user(username="test", email="a@b.com", password="x")
        assert user.max_mastodon_accounts == 1

    def test_max_bluesky_accounts_free(self):
        user = User.objects.create_user(username="test", email="a@b.com", password="x")
        assert user.max_bluesky_accounts == 1

    def test_max_mastodon_accounts_gnome(self):
        user = User.objects.create_user(username="g", email="g@b.com", password="x", plan="gnome")
        assert user.max_mastodon_accounts == 999

    def test_max_bluesky_accounts_gnome(self):
        user = User.objects.create_user(username="g", email="g@b.com", password="x", plan="gnome")
        assert user.max_bluesky_accounts == 999


class MastodonAccountTest(TestCase):
    def test_create_account(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        acct = MastodonAccount.objects.create(
            user=user,
            instance_url="https://mastodon.social",
            access_token="test_token_12345",
            mastodon_user_id="42",
            mastodon_username="testuser",
        )
        assert acct.instance_url == "https://mastodon.social"
        assert acct.mastodon_username == "testuser"
        assert acct.is_active is True
        assert acct.access_token == "test_token_12345"

    def test_foreign_key_user(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        acct = MastodonAccount.objects.create(
            user=user, instance_url="https://a", access_token="t",
            mastodon_user_id="1", mastodon_username="u",
        )
        assert user.mastodon_accounts.count() == 1
        assert user.mastodon_accounts.first() == acct

    def test_multiple_accounts(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        MastodonAccount.objects.create(
            user=user, instance_url="https://a", access_token="t1",
            mastodon_user_id="1", mastodon_username="u1",
        )
        MastodonAccount.objects.create(
            user=user, instance_url="https://b", access_token="t2",
            mastodon_user_id="2", mastodon_username="u2",
        )
        assert user.mastodon_accounts.count() == 2


class BlueskyAccountTest(TestCase):
    def test_create_account(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        acct = BlueskyAccount.objects.create(
            user=user,
            handle="user.bsky.social",
            app_password="test-password-123",
            did="did:plc:test123",
        )
        assert acct.handle == "user.bsky.social"
        assert acct.app_password == "test-password-123"
        assert acct.is_active is True

    def test_encrypted_storage(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        BlueskyAccount.objects.create(
            user=user, handle="u.bsky.social", app_password="mypass",
            did="did:plc:abc",
        )
        acct = BlueskyAccount.objects.get(user=user)
        assert acct.app_password == "mypass"


class ScoredLinkTest(TestCase):
    def test_create_link(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        link = ScoredLink.objects.create(
            user=user,
            url="https://example.com/article",
            title="Test Article",
            score=10.5,
            platform="mastodon",
            author_names="testuser",
        )
        assert link.url == "https://example.com/article"
        assert link.score == 10.5
        assert link.platform == "mastodon"

    def test_ordering_by_score(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        ScoredLink.objects.create(user=user, url="https://a.com", score=5.0, platform="m")
        ScoredLink.objects.create(user=user, url="https://b.com", score=15.0, platform="b")
        links = ScoredLink.objects.filter(user=user)
        assert links[0].score == 15.0
        assert links[1].score == 5.0


class FeedFetchJobTest(TestCase):
    def test_job_lifecycle(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        job = FeedFetchJob.objects.create(user=user, status="pending")
        assert job.status == "pending"
        job.status = "completed"
        job.save()
        assert FeedFetchJob.objects.get(user=user).status == "completed"
