"""Admin configuration for billing."""
from django.contrib import admin

from billing.models import Price


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ["name", "amount_dollars", "interval", "active", "stripe_price_id"]
    list_filter = ["active", "interval"]
