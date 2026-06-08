"""App config for feeds — sets up recurring fetch schedule."""
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _create_schedule(sender, **kwargs):
    """Create the recurring fetch schedule if it doesn't exist."""
    from django_q.models import Schedule

    Schedule.objects.update_or_create(
        name="fetch_all_feeds",
        defaults={
            "func": "django.core.management.call_command",
            "args": "('fetch_all_feeds',)",
            "schedule_type": Schedule.MINUTES,
            "minutes": 5,
            "repeats": -1,
        },
    )
    Schedule.objects.update_or_create(
        name="refresh_public_feed",
        defaults={
            "func": "django.core.management.call_command",
            "args": "('refresh_public_feed',)",
            "schedule_type": Schedule.MINUTES,
            "minutes": 15,
            "repeats": -1,
        },
    )


class FeedsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feeds"

    def ready(self):
        post_migrate.connect(_create_schedule, sender=self)
