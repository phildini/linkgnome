"""Billing views — Stripe Checkout integration."""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.models import User

logger = logging.getLogger(__name__)


@login_required
def create_checkout(request):
    price_id = settings.STRIPE_GNOME_PRICE_ID
    if not price_id:
        messages.error(request, "Pricing is not configured yet. Check back soon.")
        return redirect("feeds:pricing")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            client_reference_id=str(request.user.id),
            customer_email=request.user.email,
            success_url=request.build_absolute_uri("/billing/success/"),
            cancel_url=request.build_absolute_uri("/billing/cancel/"),
        )
        return redirect(session.url, code=303)
    except Exception as e:
        logger.exception("Failed to create Stripe checkout session")
        messages.error(request, f"Could not start checkout: {e}")
        return redirect("feeds:pricing")


@login_required
def checkout_success(request):
    user = request.user
    if user.plan == "free":
        user.plan = "gnome"
        user.save(update_fields=["plan"])
        messages.success(request, "Welcome to Gnome! Your account has been upgraded.")
    return redirect("feeds:dashboard")


@login_required
def checkout_cancel(request):
    messages.info(request, "Checkout cancelled. You're still on the Free plan.")
    return redirect("feeds:pricing")
