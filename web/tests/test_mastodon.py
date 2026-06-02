"""Tests for Mastodon OAuth helpers."""
import respx
from django.test import TestCase

from accounts.mastodon import (
    register_instance_app,
    build_authorize_url,
    exchange_code,
    fetch_identity,
    clear_instance_cache,
)
from accounts.models import InstanceApp


class RegisterInstanceAppTest(TestCase):
    @respx.mock
    def test_register_new_instance(self):
        url = "https://mastodon.social"
        respx.post(f"{url}/api/v1/apps").respond(
            200, json={
                "client_id": "client123", "client_secret": "secret456",
            }
        )
        result = register_instance_app(url, "https://example.com/callback")
        assert result["client_id"] == "client123"
        assert result["client_secret"] == "secret456"
        assert InstanceApp.objects.filter(instance_url=url).exists()

    @respx.mock
    def test_register_uses_cache(self):
        url = "https://hachyderm.io"
        InstanceApp.objects.create(
            instance_url=url, client_id="cached_id", client_secret="cached_secret",
        )
        result = register_instance_app(url, "https://example.com/callback")
        assert result["client_id"] == "cached_id"
        assert result["client_secret"] == "cached_secret"

    @respx.mock
    def test_register_fails_on_api_error(self):
        url = "https://mastodon.social"
        respx.post(f"{url}/api/v1/apps").respond(500)
        with self.assertRaises(Exception):
            register_instance_app(url, "https://example.com/callback")

    def test_clear_cache(self):
        InstanceApp.objects.create(
            instance_url="https://a.com", client_id="a", client_secret="b",
        )
        clear_instance_cache("https://a.com")
        assert not InstanceApp.objects.filter(instance_url="https://a.com").exists()


class BuildAuthorizeUrlTest(TestCase):
    def test_builds_url(self):
        url = build_authorize_url(
            "https://mastodon.social", "client123", "https://example.com/cb"
        )
        assert "mastodon.social/oauth/authorize" in url
        assert "client_id=client123" in url
        assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcb" in url
        assert "response_type=code" in url
        assert "scope=read%3Astatuses+read%3Anotifications" in url


@respx.mock
class ExchangeCodeTest(TestCase):
    def test_exchanges_code(self):
        url = "https://mastodon.social"
        respx.post(f"{url}/oauth/token").respond(
            200, json={
                "access_token": "token_abc",
                "token_type": "Bearer",
                "scope": "read:statuses",
                "created_at": 1234567890,
            }
        )
        result = exchange_code(url, "cid", "csec", "authcode", "https://ex.com/cb")
        assert result["access_token"] == "token_abc"

    def test_exchange_fails(self):
        url = "https://mastodon.social"
        respx.post(f"{url}/oauth/token").respond(400)
        with self.assertRaises(Exception):
            exchange_code(url, "cid", "csec", "badcode", "https://ex.com/cb")


@respx.mock
class FetchIdentityTest(TestCase):
    def test_fetch_identity(self):
        url = "https://mastodon.social"
        respx.get(f"{url}/api/v1/accounts/verify_credentials").respond(
            200, json={"id": "42", "username": "testuser", "display_name": "Test"}
        )
        result = fetch_identity(url, "token_abc")
        assert result["id"] == "42"
        assert result["username"] == "testuser"

    def test_fetch_identity_fails(self):
        url = "https://mastodon.social"
        respx.get(f"{url}/api/v1/accounts/verify_credentials").respond(403)
        with self.assertRaises(Exception):
            fetch_identity(url, "bad_token")
