"""Billing models for Stripe integration."""
from django.db import models


class Price(models.Model):
    name = models.CharField(max_length=50)
    stripe_price_id = models.CharField(max_length=100, blank=True)
    amount_dollars = models.IntegerField()
    interval = models.CharField(max_length=10, choices=[
        ("month", "Monthly"),
        ("year", "Yearly"),
    ])
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (${self.amount_dollars}/{self.interval})"
