"""Stripe webhook handler."""
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import User

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning("Invalid Stripe webhook signature: %s", e)
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                if user.plan == "free":
                    user.plan = "gnome"
                    user.stripe_customer_id = session.get("customer", "")
                    user.save(update_fields=["plan", "stripe_customer_id"])
                    logger.info("Upgraded user %s to Gnome via webhook", user_id)
            except User.DoesNotExist:
                logger.warning("Webhook referenced unknown user: %s", user_id)

    return HttpResponse(status=200)
