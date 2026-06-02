"""User and social account models."""
import base64

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


def _get_fernet() -> Fernet:
    """Build a Fernet cipher from Django's SECRET_KEY."""
    raw = settings.SECRET_KEY.encode()[:32].ljust(32, b"x")
    return Fernet(base64.urlsafe_b64encode(raw))


class EncryptedField(models.TextField):
    """Stores values encrypted at rest using Django's SECRET_KEY."""

    def get_prep_value(self, value):
        if value is None:
            return None
        return _get_fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except Exception:
            return value


class User(AbstractUser):
    plan = models.CharField(max_length=20, default="free", choices=[
        ("free", "Free"),
        ("gnome", "Gnome"),
    ])
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    last_refresh_at = models.DateTimeField(null=True, blank=True)
    email_verified = models.BooleanField(default=False)

    @property
    def max_mastodon_accounts(self) -> int:
        return {"free": 1, "gnome": 999}[self.plan]

    @property
    def max_bluesky_accounts(self) -> int:
        return {"free": 1, "gnome": 999}[self.plan]

    @property
    def refresh_cooldown_seconds(self) -> int:
        return 300

    @property
    def is_fully_activated(self) -> bool:
        return self.is_active and self.email_verified


class InstanceApp(models.Model):
    instance_url = models.CharField(max_length=255, unique=True)
    client_id = models.TextField()
    client_secret = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class MastodonAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mastodon_accounts")
    instance_url = models.CharField(max_length=255)
    access_token = EncryptedField()
    mastodon_user_id = models.CharField(max_length=100)
    mastodon_username = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "instance_url", "mastodon_user_id"]


class BlueskyAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bluesky_accounts")
    handle = models.CharField(max_length=255)
    app_password = EncryptedField()
    did = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "handle"]
