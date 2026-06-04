"""Tests for persistent Link models (Identity, Follow, Link)."""
from datetime import datetime, timezone

from django.test import TestCase

from accounts.models import User
from links.models import Follow, Identity, Link


class IdentityTest(TestCase):
    def test_create_identity(self):
        identity = Identity.objects.create(
            platform="mastodon",
            username="testuser",
            display_name="Test User",
            platform_user_id="12345",
            instance_url="mastodon.social",
        )
        assert identity.username == "testuser"
        assert identity.platform == "mastodon"
        assert str(identity) == "@testuser@mastodon.social"

    def test_unique_platform_user_id(self):
        Identity.objects.create(
            platform="mastodon", username="u1", platform_user_id="1",
        )
        with self.assertRaises(Exception):
            Identity.objects.create(
                platform="mastodon", username="u2", platform_user_id="1",
            )

    def test_same_id_different_platform(self):
        Identity.objects.create(
            platform="mastodon", username="u", platform_user_id="1",
        )
        Identity.objects.create(
            platform="bluesky", username="u", platform_user_id="1",
        )
        assert Identity.objects.count() == 2


class FollowTest(TestCase):
    def test_create_follow(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        identity = Identity.objects.create(
            platform="mastodon", username="other", platform_user_id="42",
        )
        follow = Follow.objects.create(user=user, identity=identity)
        assert follow.user == user
        assert follow.identity == identity
        assert str(follow) == "t → @other"

    def test_unique_user_identity(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        identity = Identity.objects.create(
            platform="mastodon", username="other", platform_user_id="42",
        )
        Follow.objects.create(user=user, identity=identity)
        with self.assertRaises(Exception):
            Follow.objects.create(user=user, identity=identity)

    def test_reverse_relations(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        ident = Identity.objects.create(
            platform="mastodon", username="other", platform_user_id="42",
        )
        Follow.objects.create(user=user, identity=ident)
        assert user.follows.count() == 1
        assert ident.followed_by.count() == 1


class LinkTest(TestCase):
    def setUp(self):
        self.identity = Identity.objects.create(
            platform="mastodon", username="author", platform_user_id="1",
        )

    def test_create_link(self):
        link = Link.objects.create(
            url="https://example.com/article",
            canonical_url="https://example.com/article",
            posted_by=self.identity,
            posted_at=datetime.now(timezone.utc),
            platform_post_id="post_1",
            score=10.5,
            like_count=10,
            boost_count=5,
        )
        assert link.url == "https://example.com/article"
        assert link.score == 10.5
        assert link.like_count == 10
        assert link.boost_count == 5

    def test_unique_url_per_post(self):
        Link.objects.create(
            url="https://ex.com/a", canonical_url="https://ex.com/a",
            posted_by=self.identity, posted_at=datetime.now(timezone.utc),
            platform_post_id="p1",
        )
        with self.assertRaises(Exception):
            Link.objects.create(
                url="https://ex.com/a", canonical_url="https://ex.com/a",
                posted_by=self.identity, posted_at=datetime.now(timezone.utc),
                platform_post_id="p1",
            )

    def test_same_url_different_post(self):
        Link.objects.create(
            url="https://ex.com/a", canonical_url="https://ex.com/a",
            posted_by=self.identity, posted_at=datetime.now(timezone.utc),
            platform_post_id="p1",
        )
        Link.objects.create(
            url="https://ex.com/a", canonical_url="https://ex.com/a",
            posted_by=self.identity, posted_at=datetime.now(timezone.utc),
            platform_post_id="p2",
        )
        assert Link.objects.count() == 2

    def test_ordering_by_score(self):
        Link.objects.create(
            url="https://ex.com/a", canonical_url="https://ex.com/a",
            posted_by=self.identity, posted_at=datetime.now(timezone.utc),
            platform_post_id="p1", score=5.0,
        )
        Link.objects.create(
            url="https://ex.com/b", canonical_url="https://ex.com/b",
            posted_by=self.identity, posted_at=datetime.now(timezone.utc),
            platform_post_id="p2", score=15.0,
        )
        links = Link.objects.all()
        assert links[0].score == 15.0
        assert links[1].score == 5.0

    def test_identity_links_relation(self):
        Link.objects.create(
            url="https://ex.com/a", canonical_url="https://ex.com/a",
            posted_by=self.identity, posted_at=datetime.now(timezone.utc),
            platform_post_id="p1",
        )
        assert self.identity.links.count() == 1
