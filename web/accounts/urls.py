"""Account URL configuration."""
from django.urls import path
from accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("send-link/", views.login_send_link, name="send_link"),
    path("settings/", views.settings_view, name="settings"),
    path("mastodon/connect/", views.connect_mastodon, name="connect_mastodon"),
    path("mastodon/callback/", views.mastodon_callback, name="mastodon_callback"),
    path("mastodon/disconnect/<int:account_id>/", views.disconnect_mastodon, name="disconnect_mastodon"),
    path("bluesky/connect/", views.connect_bluesky, name="connect_bluesky"),
    path("bluesky/disconnect/<int:account_id>/", views.disconnect_bluesky, name="disconnect_bluesky"),
]
