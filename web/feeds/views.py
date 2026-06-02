"""Feed views — dashboard, HTMX endpoints."""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_q.tasks import async_task

from feeds.models import FeedFetchJob, ScoredLink

PAGE_SIZE = 25


@login_required
def dashboard(request):
    user = request.user
    platform = request.GET.get("platform", "all")
    links = _filter_links(user, platform)
    paginator = Paginator(links, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", 1))

    can_refresh, cooldown_remaining = _check_cooldown(user)

    return render(request, "feeds/dashboard.html", {
        "links": page,
        "can_refresh": can_refresh,
        "cooldown_remaining": cooldown_remaining,
        "has_mastodon": user.mastodon_accounts.filter(is_active=True).exists(),
        "has_bluesky": user.bluesky_accounts.filter(is_active=True).exists(),
        "is_activated": user.is_fully_activated,
        "current_platform": platform,
    })


@login_required
def feed_table(request):
    user = request.user
    platform = request.GET.get("platform", "all")
    links = _filter_links(user, platform)
    paginator = Paginator(links, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", 1))
    return render(request, "feeds/feed_table.html", {
        "links": page,
        "current_platform": platform,
    })


def _filter_links(user, platform: str):
    qs = ScoredLink.objects.filter(user=user)
    if platform == "mastodon":
        qs = qs.filter(platform__icontains="mastodon")
    elif platform == "bluesky":
        qs = qs.filter(platform__icontains="bluesky")
    return qs


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

    user.last_refresh_at = timezone.now()
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
    latest_job = (
        FeedFetchJob.objects.filter(user=user)
        .order_by("-requested_at")
        .first()
    )

    if latest_job and latest_job.status == "completed":
        links = _filter_links(user, platform)
        paginator = Paginator(links, PAGE_SIZE)
        page = paginator.get_page(1)
        return render(request, "feeds/feed_table.html", {
            "links": page,
            "current_platform": platform,
        })

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
    elapsed = timezone.now() - user.last_refresh_at
    cooldown = timedelta(seconds=user.refresh_cooldown_seconds)
    if elapsed >= cooldown:
        return True, 0
    remaining = int((cooldown - elapsed).total_seconds())
    return False, remaining
