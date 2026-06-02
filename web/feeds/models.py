"""Feed-related models."""
from django.db import models
from django.conf import settings


class FeedFetchJob(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fetch_jobs"
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]


class ScoredLink(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scored_links"
    )
    url = models.URLField(max_length=2000)
    title = models.CharField(max_length=1000, blank=True)
    score = models.FloatField(db_index=True)
    platform = models.CharField(
        max_length=50,
        help_text="Platform label e.g. 'mastodon', 'bluesky', or 'mastodon+bluesky'",
    )
    author_names = models.CharField(max_length=500, blank=True)
    author_post_urls = models.JSONField(default=list, blank=True)
    post_count = models.IntegerField(default=0)
    boost_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    last_posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-score"]
        unique_together = ["user", "url"]
