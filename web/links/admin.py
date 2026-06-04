"""Admin configuration for links app."""
from django.contrib import admin

from links.models import Follow, Identity, Link


@admin.register(Identity)
class IdentityAdmin(admin.ModelAdmin):
    list_display = ["username", "platform", "instance_url", "first_seen_at"]
    list_filter = ["platform"]
    search_fields = ["username", "display_name"]


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ["user", "identity", "created_at"]
    list_filter = ["user"]
    autocomplete_fields = ["user", "identity"]


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ["__str__", "posted_by", "score", "posted_at", "like_count"]
    list_filter = ["posted_by__platform"]
    search_fields = ["url", "title"]
    autocomplete_fields = ["posted_by"]
