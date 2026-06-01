"""Feed URL configuration."""
from django.urls import path
from feeds import views

app_name = "feeds"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("feeds/table/", views.feed_table, name="feed_table"),
    path("feeds/refresh/", views.refresh_feeds, name="refresh_feeds"),
    path("feeds/refresh-button/", views.refresh_button, name="refresh_button"),
]
