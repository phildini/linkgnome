"""Management command to refresh the public feed (top links across all users)."""
from collections import OrderedDict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone

from feeds.models import ScoredLink
from links.models import PublicLink


class Command(BaseCommand):
    help = "Aggregate top links across all users and store in PublicLink"

    def handle(self, **options):
        cutoff = timezone.now() - timedelta(hours=24)

        top_urls = (
            ScoredLink.objects
            .filter(last_seen_at__gte=cutoff)
            .values("url")
            .annotate(agg_score=Sum("score"))
            .order_by("-agg_score")[:25]
            .values_list("url", flat=True)
        )

        PublicLink.objects.all().delete()

        if not top_urls:
            self.stdout.write("No links found for public feed")
            return

        batch = []
        for url in top_urls:
            qs = ScoredLink.objects.filter(url=url, last_seen_at__gte=cutoff)
            best = qs.order_by("-score").first()
            stats = qs.aggregate(
                total_score=Sum("score"),
                total_post=Sum("post_count"),
                total_boost=Sum("boost_count"),
                total_like=Sum("like_count"),
                num_users=Count("user", distinct=True),
            )
            batch.append(PublicLink(
                url=best.url,
                title=best.title,
                score=round(stats["total_score"] or best.score, 1),
                platform=best.platform,
                author_names=best.author_names,
                author_post_urls=best.author_post_urls,
                num_users=stats["num_users"] or 0,
                post_count=stats["total_post"] or best.post_count,
                boost_count=stats["total_boost"] or best.boost_count,
                like_count=stats["total_like"] or best.like_count,
                last_posted_at=best.last_posted_at,
            ))

        PublicLink.objects.bulk_create(batch)
        self.stdout.write(f"Public feed refreshed with {len(batch)} links")
