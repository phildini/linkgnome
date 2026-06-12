"""Feed views — landing, dashboard, HTMX endpoints."""
from collections import OrderedDict
from datetime import datetime, timedelta, timezone as dt_tz

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone as django_tz
from django.views.decorators.http import require_POST
from django_q.tasks import async_task

from feeds.models import FeedFetchJob, ScoredLink
from billing.models import Price

PAGE_SIZE = 25

TIME_RANGES = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "all": None,
}


def _effective_time_range(user, requested: str) -> str:
    """Return the actual time range a user can access."""
    if requested in TIME_RANGES:
        return requested
    return "24h"


def _get_top_public_links():
    links = cache.get("top_public_links")
    if links is not None:
        return links

    cutoff = django_tz.now() - timedelta(hours=24)
    qs = ScoredLink.objects.filter(last_seen_at__gte=cutoff).order_by("-score")

    seen = OrderedDict()
    for sl in qs.iterator():
        if sl.url not in seen:
            seen[sl.url] = sl
        if len(seen) >= 25:
            break

    links = list(seen.values())
    cache.set("top_public_links", links, 60 * 15)
    return links


def landing(request):
    return render(request, "feeds/landing.html", {"public_links": _get_top_public_links()})


def pricing(request):
    prices = Price.objects.filter(active=True).order_by("amount_dollars")
    return render(request, "feeds/pricing.html", {"prices": prices})


@login_required
def dashboard(request):
    user = request.user
    platform = request.GET.get("platform", "all")
    time_range = _effective_time_range(user, request.GET.get("range", "24h"))
    links = _filter_links(user, platform, time_range)
    paginator = Paginator(links, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", 1))

    can_refresh, cooldown_remaining = _check_cooldown(user)

    return render(request, "feeds/dashboard.html", {
        "links": page,
        "public_links": _get_top_public_links(),
        "can_refresh": can_refresh,
        "cooldown_remaining": cooldown_remaining,
        "has_mastodon": user.mastodon_accounts.filter(is_active=True).exists(),
        "has_bluesky": user.bluesky_accounts.filter(is_active=True).exists(),
        "is_activated": user.is_fully_activated,
        "current_platform": platform,
        "current_range": time_range,
    })


@login_required
def feed_table(request):
    user = request.user
    platform = request.GET.get("platform", "all")
    time_range = _effective_time_range(user, request.GET.get("range", "24h"))
    links = _filter_links(user, platform, time_range)
    paginator = Paginator(links, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", 1))
    ctx = {
        "links": page,
        "current_platform": platform,
        "current_range": time_range,
    }

    if request.headers.get("HX-Request"):
        content = render(request, "feeds/feed_content.html", ctx)
        oob = render(request, "feeds/filter_oob.html", ctx)
        return HttpResponse(content.content + oob.content)

    return render(request, "feeds/feed_content.html", ctx)


def _filter_links(user, platform: str, time_range: str = "24h"):
    qs = ScoredLink.objects.filter(user=user)
    cutoff = TIME_RANGES.get(time_range)
    if cutoff:
        if time_range == "24h":
            qs = qs.filter(last_seen_at__gte=datetime.now(dt_tz.utc) - cutoff)
        else:
            qs = qs.filter(first_seen_at__gte=datetime.now(dt_tz.utc) - cutoff)
    if platform == "mastodon":
        qs = qs.filter(platform__icontains="mastodon")
    elif platform == "bluesky":
        qs = qs.filter(platform__icontains="bluesky")
    return qs.order_by("-score")


@login_required
@require_POST
def refresh_feeds(request):
    user = request.user
    can_refresh, cooldown_remaining = _check_cooldown(user)

    if not can_refresh:
        return render(request, "feeds/refresh_button.html", {
            "can_refresh": False,
            "cooldown_remaining": cooldown_remaining,
        })

    user.last_refresh_at = django_tz.now()
    user.save(update_fields=["last_refresh_at"])

    async_task("feeds.tasks.fetch_user_feeds", user.id)

    response = render(request, "feeds/refresh_button.html", {
        "can_refresh": False,
        "cooldown_remaining": user.refresh_cooldown_seconds,
    })
    response["HX-Trigger"] = "startPolling"
    return response


@login_required
def feed_status(request):
    user = request.user
    platform = request.GET.get("platform", "all")
    time_range = _effective_time_range(user, request.GET.get("range", "24h"))
    latest_job = (
        FeedFetchJob.objects.filter(user=user)
        .order_by("-requested_at")
        .first()
    )

    if latest_job and latest_job.status == "completed":
        links = _filter_links(user, platform, time_range)
        paginator = Paginator(links, PAGE_SIZE)
        page = paginator.get_page(1)
        ctx = {"links": page, "current_platform": platform, "current_range": time_range}
        content = render(request, "feeds/feed_content.html", ctx)
        oob = render(request, "feeds/filter_oob.html", ctx)
        return HttpResponse(content.content + oob.content)

    return HttpResponse(status=204)


@login_required
def refresh_button(request):
    user = request.user
    can_refresh, cooldown_remaining = _check_cooldown(user)
    return render(request, "feeds/refresh_button.html", {
        "can_refresh": can_refresh,
        "cooldown_remaining": cooldown_remaining,
    })


def _check_cooldown(user):
    if not user.last_refresh_at:
        return True, 0
    elapsed = django_tz.now() - user.last_refresh_at
    cooldown = timedelta(seconds=user.refresh_cooldown_seconds)
    if elapsed >= cooldown:
        return True, 0
    remaining = int((cooldown - elapsed).total_seconds())
    return False, remaining
