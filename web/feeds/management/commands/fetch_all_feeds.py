"""Management command to enqueue feed fetches for all active users."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django_q.tasks import async_task


class Command(BaseCommand):
    help = "Enqueue feed fetches for all active users"

    def handle(self, *args, **options):
        User = get_user_model()
        users = User.objects.filter(
            is_active=True,
            email_verified=True,
        )

        count = 0
        for user in users:
            has_mastodon = getattr(user, "mastodon_account", None)
            has_bluesky = getattr(user, "bluesky_account", None)
            if has_mastodon or has_bluesky:
                async_task("feeds.tasks.fetch_user_feeds", user.id)
                count += 1

        self.stdout.write(f"Enqueued feed fetches for {count} users")
