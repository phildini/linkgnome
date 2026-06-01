"""Admin configuration for accounts."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User, InstanceApp, MastodonAccount, BlueskyAccount


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "plan", "email_verified", "is_active", "date_joined"]
    list_filter = ["plan", "email_verified", "is_active"]
    search_fields = ["username", "email"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("LinkGnome", {"fields": ("plan", "stripe_customer_id", "email_verified", "last_refresh_at")}),
    )


@admin.register(InstanceApp)
class InstanceAppAdmin(admin.ModelAdmin):
    list_display = ["instance_url", "created_at"]


@admin.register(MastodonAccount)
class MastodonAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "instance_url", "mastodon_username", "is_active", "created_at"]
    list_filter = ["is_active"]


@admin.register(BlueskyAccount)
class BlueskyAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "handle", "is_active", "created_at"]
    list_filter = ["is_active"]
