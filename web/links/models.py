"""Models for persistent link storage."""
from django.conf import settings
from django.db import models


class Identity(models.Model):
    """Universal person/profile across platforms."""

    platform = models.CharField(max_length=20)
    username = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(blank=True)
    platform_user_id = models.CharField(max_length=255)
    instance_url = models.CharField(max_length=255, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("platform", "platform_user_id")]
        verbose_name_plural = "identities"

    def __str__(self):
        base = f"@{self.username}"
        if self.instance_url:
            base += f"@{self.instance_url}"
        return base


class Follow(models.Model):
    """Which Identities a LinkGnome user follows."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follows"
    )
    identity = models.ForeignKey(
        Identity, on_delete=models.CASCADE, related_name="followed_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "identity")]

    def __str__(self):
        return f"{self.user.username} → {self.identity}"


class Link(models.Model):
    """A link shared on social media, persistently stored."""

    url = models.URLField(max_length=2000)
    canonical_url = models.URLField(max_length=2000, blank=True)
    title = models.CharField(max_length=1000, blank=True)
    score = models.FloatField(default=0)
    posted_by = models.ForeignKey(
        Identity, on_delete=models.CASCADE, related_name="links"
    )
    posted_at = models.DateTimeField()
    post_url = models.URLField(max_length=2000, blank=True)
    platform_post_id = models.CharField(max_length=500)
    post_text = models.TextField(blank=True)
    like_count = models.IntegerField(default=0)
    boost_count = models.IntegerField(default=0)
    reply_count = models.IntegerField(default=0)
    post_count = models.IntegerField(default=1)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score"]
        unique_together = [("canonical_url", "platform_post_id")]
        indexes = [
            models.Index(fields=["-posted_at"]),
            models.Index(fields=["-score"]),
        ]

    def __str__(self):
        return f"{self.canonical_url or self.url} (score: {self.score})"
