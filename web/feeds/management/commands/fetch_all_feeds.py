"""Management command to enqueue feed fetches for users due for refresh.

Runs every 5 minutes via django-q2 schedule. Each user is refreshed
once per 60 minutes, staggered by their signup minute."""
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django_q.tasks import async_task


class Command(BaseCommand):
    help = "Enqueue feed fetches for users due for staggered refresh"

    def handle(self, *args, **options):
        now = datetime.now()
        window_start = (now.minute // 5) * 5
        window_end = window_start + 5

        User = get_user_model()
        users = User.objects.filter(
            is_active=True,
            email_verified=True,
        )

        count = 0
        for user in users:
            signup_minute = user.date_joined.minute
            if window_start <= signup_minute < window_end:
                has_mastodon = getattr(user, "mastodon_account", None)
                has_bluesky = getattr(user, "bluesky_account", None)
                if has_mastodon or has_bluesky:
                    async_task("feeds.tasks.fetch_user_feeds", user.id)
                    count += 1

        if count:
            self.stdout.write(f"Enqueued feed fetches for {count} users")
