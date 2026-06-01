"""Admin configuration for feeds."""
from django.contrib import admin

from feeds.models import ScoredLink, FeedFetchJob


@admin.register(ScoredLink)
class ScoredLinkAdmin(admin.ModelAdmin):
    list_display = ["user", "score", "platform", "url", "last_seen_at"]
    list_filter = ["platform", "user"]
    search_fields = ["url", "title"]


@admin.register(FeedFetchJob)
class FeedFetchJobAdmin(admin.ModelAdmin):
    list_display = ["user", "status", "requested_at", "completed_at"]
    list_filter = ["status"]
