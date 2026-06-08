"""Root URL configuration for linkgnome-web."""
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from billing.webhook import stripe_webhook


def health_check(request):
    return HttpResponse("ok")


urlpatterns = [
    path("health/", health_check),
    path("admin/", admin.site.urls),
    path("auth/", include("stagedoor.urls", namespace="stagedoor")),
    path("accounts/", include("accounts.urls")),
    path("billing/", include("billing.urls")),
    path("stripe/webhook/", stripe_webhook),
    path("", include("feeds.urls")),
]
