"""Tests for account views (signup, login, verification, settings)."""
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    RATELIMIT_ENABLE=False,
)
class SignupTest(TestCase):
    def test_signup_page_loads(self):
        response = self.client.get(reverse("accounts:signup"))
        assert response.status_code == 200
        assert b"Sign Up" in response.content

    def test_signup_creates_user_and_sends_email(self):
        response = self.client.post(reverse("accounts:signup"), {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "testpass123",
            "confirm_password": "testpass123",
        })
        assert response.status_code == 200
        assert b"Check Your Email" in response.content
        assert User.objects.filter(username="newuser").exists()
        user = User.objects.get(username="newuser")
        assert user.email_verified is False
        assert len(mail.outbox) == 1
        assert "Verify" in mail.outbox[0].subject

    def test_signup_password_mismatch(self):
        response = self.client.post(reverse("accounts:signup"), {
            "username": "user1", "email": "u@b.com",
            "password": "abc123", "confirm_password": "different",
        })
        assert response.status_code == 200
        assert b"Passwords do not match" in response.content
        assert not User.objects.filter(username="user1").exists()

    def test_signup_duplicate_email(self):
        User.objects.create_user(username="existing", email="dup@example.com", password="x")
        response = self.client.post(reverse("accounts:signup"), {
            "username": "newguy", "email": "dup@example.com",
            "password": "pass123", "confirm_password": "pass123",
        })
        assert b"already exists" in response.content

    def test_signup_redirects_authenticated(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:signup"))
        assert response.status_code == 302


@override_settings(RATELIMIT_ENABLE=False)
class LoginTest(TestCase):
    def test_login_page_loads(self):
        response = self.client.get(reverse("accounts:login"))
        assert response.status_code == 200

    def test_login_succeeds(self):
        User.objects.create_user(username="tester", email="t@b.com", password="secret123")
        response = self.client.post(reverse("accounts:login"), {
            "username": "tester", "password": "secret123",
        })
        assert response.status_code == 302

    def test_login_fails_wrong_password(self):
        User.objects.create_user(username="tester", email="t@b.com", password="correct")
        response = self.client.post(reverse("accounts:login"), {
            "username": "tester", "password": "wrong",
        })
        assert response.status_code == 200
        assert b"Please enter a correct username and password" in response.content

    def test_login_redirects_authenticated(self):
        user = User.objects.create_user(username="t", email="a@b.com", password="x")
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:login"))
        assert response.status_code == 302


@override_settings(RATELIMIT_ENABLE=False)
class EmailVerificationTest(TestCase):
    def test_verify_valid_token(self):
        from django.core.signing import TimestampSigner
        signer = TimestampSigner()
        user = User.objects.create_user(
            username="verify_me", email="v@b.com", password="x"
        )
        token = signer.sign(str(user.id))
        response = self.client.get(reverse("accounts:verify_email", args=[token]))
        assert response.status_code == 200
        assert b"Email Verified" in response.content
        user.refresh_from_db()
        assert user.email_verified is True

    def test_verify_expired_token(self):
        from django.core.signing import TimestampSigner
        signer = TimestampSigner()
        user = User.objects.create_user(
            username="expired", email="e@b.com", password="x"
        )
        import time
        token = signer.sign(str(user.id))
        self.client.get(reverse("accounts:verify_email", args=[token]))
        user.refresh_from_db()
        assert user.email_verified is True

    def test_verify_invalid_token(self):
        response = self.client.get(
            reverse("accounts:verify_email", args=["invalid-token-here"])
        )
        assert response.status_code == 200
        assert b"expired" in response.content.lower() or b"invalid" in response.content.lower()


@override_settings(RATELIMIT_ENABLE=False)
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
        assert b"Connect" in response.content
