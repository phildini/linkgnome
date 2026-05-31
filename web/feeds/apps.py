"""App config for feeds — sets up recurring fetch schedule."""
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _create_schedule(sender, **kwargs):
    """Create the recurring fetch schedule if it doesn't exist."""
    from django_q.models import Schedule

    Schedule.objects.get_or_create(
        func="django.core.management.call_command",
        name="fetch_all_feeds",
        defaults={
            "args": "fetch_all_feeds",
            "schedule_type": Schedule.MINUTES,
            "minutes": 5,
            "repeats": -1,
        },
    )


class FeedsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feeds"

    def ready(self):
        post_migrate.connect(_create_schedule, sender=self)
