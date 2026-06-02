"""Billing models — stub for future Stripe integration."""
from django.db import models
from django.conf import settings


class Plan(models.Model):
    name = models.CharField(max_length=50, unique=True)
    stripe_price_id = models.CharField(max_length=100, blank=True)
    max_social_accounts = models.IntegerField(default=1)
    refresh_cooldown_seconds = models.IntegerField(default=1800)
    history_days = models.IntegerField(default=1)
    price_display = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name
