"""Tests for account views (login, settings)."""
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User


class LoginTest(TestCase):
    def test_login_page_loads(self):
        response = self.client.get(reverse("accounts:login"))
        assert response.status_code == 200

    def test_login_redirects_authenticated(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:login"))
        assert response.status_code == 302


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class StagedoorLoginTest(TestCase):
    def test_login_post_sends_magic_link(self):
        response = self.client.post(
            reverse("stagedoor:login"),
            {"contact": "newuser@example.com"},
        )
        assert response.status_code == 302
        from django.core import mail
        assert len(mail.outbox) == 1
        assert "login" in mail.outbox[0].subject.lower()

    def test_login_post_invalid_email(self):
        response = self.client.post(
            reverse("stagedoor:login"),
            {"contact": "not-an-email"},
        )
        assert response.status_code == 302

    def test_token_login_creates_user_and_logs_in(self):
        from stagedoor.models import Email, AuthToken

        email_obj, _ = Email.objects.get_or_create(email="new@example.com")
        token = AuthToken.objects.create(token="testtoken123", email=email_obj)
        response = self.client.get(
            reverse("stagedoor:token-login", args=[token.token])
        )
        assert response.status_code == 302
        assert User.objects.filter(email="new@example.com").exists()
        user = User.objects.get(email="new@example.com")
        assert user.is_authenticated

    def test_token_login_invalid_token(self):
        response = self.client.get(
            reverse("stagedoor:token-login", args=["invalidtoken"])
        )
        assert response.status_code == 302


class SettingsTest(TestCase):
    def test_settings_requires_login(self):
        response = self.client.get(reverse("accounts:settings"))
        assert response.status_code == 302

    def test_settings_shows_account_info(self):
        user = User.objects.create_user(
            username="set_user", email="s@b.com", password="x"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:settings"))
        assert response.status_code == 200
        assert b"set_user" in response.content

    def test_settings_shows_disconnected_status(self):
        user = User.objects.create_user(
            username="alone", email="a@b.com", password="x",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:settings"))
        assert b"Not connected" in response.content
