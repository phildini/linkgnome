"""Account URL configuration."""
from django.urls import path
from accounts import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("verify/<token>/", views.verify_email, name="verify_email"),
    path("settings/", views.settings_view, name="settings"),
    path("mastodon/connect/", views.connect_mastodon, name="connect_mastodon"),
    path("mastodon/callback/", views.mastodon_callback, name="mastodon_callback"),
    path("mastodon/disconnect/", views.disconnect_mastodon, name="disconnect_mastodon"),
    path("bluesky/connect/", views.connect_bluesky, name="connect_bluesky"),
    path("bluesky/disconnect/", views.disconnect_bluesky, name="disconnect_bluesky"),
]
