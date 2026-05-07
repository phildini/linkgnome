"""Terminal UI for displaying ranked links."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.table import Table

from linkgnome.cache import FeedCache
from linkgnome.config import LinkgnomeSettings
from linkgnome.fetchers.base import Platform, Post, TimelineType
from linkgnome.fetchers.mastodon import MastodonFetcher
from linkgnome.fetchers.bluesky import BlueskyFetcher
from linkgnome.scorer import ScoredLink, score_links

console = Console()

PLATFORM_ICON = {
    Platform.MASTODON: "🟣",
    Platform.BLUESKY: "🔵",
}


def run_tui(
    settings: LinkgnomeSettings,
    hours: int = 24,
    page: int = 1,
    platform_filter: str | None = None,
) -> None:
    """Run the terminal UI to display ranked links."""
    console.print("[bold cyan]\nFetching links from your feeds...[/bold cyan]\n")

    cache = FeedCache(ttl_seconds=settings.cache_ttl_seconds)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    posts = _fetch_all_posts(settings, cache, platform_filter, cutoff)

    if not posts:
        console.print("[yellow]No posts found in the specified time period.[/yellow]")
        return

    scored_links = score_links(posts, period_hours=hours)

    if not scored_links:
        console.print("[yellow]No links found in the specified time period.[/yellow]")
        return

    _display_links_page(scored_links, page, settings.page_size)


def _fetch_all_posts(
    settings: LinkgnomeSettings,
    cache: FeedCache,
    platform_filter: str | None = None,
    cutoff: datetime | None = None,
) -> list[Post]:
    """Fetch posts from both platforms synchronously."""
    import asyncio

    posts: list[Post] = []

    mastodon_enabled = settings.mastodon.enabled and platform_filter in (
        None,
        "mastodon",
    )
    bluesky_enabled = settings.bluesky.enabled and platform_filter in (None, "bluesky")

    if not mastodon_enabled and not bluesky_enabled:
        return posts

    async def _fetch_both():
        tasks = []
        if mastodon_enabled:
            tasks.append(_fetch_mastodon_posts(settings, cache, cutoff))
        if bluesky_enabled:
            tasks.append(_fetch_bluesky_posts(settings, cache, cutoff))
        results = await asyncio.gather(*tasks)
        for result_list in results:
            posts.extend(result_list)

    asyncio.run(_fetch_both())
    return posts


async def _fetch_mastodon_posts(
    settings: LinkgnomeSettings,
    cache: FeedCache,
    cutoff: datetime | None = None,
) -> list[Post]:
    """Fetch posts from Mastodon with pagination and cutoff."""
    cached = cache.get_feed("mastodon", "home")
    if cached is not None:
        return [
            Post(
                id=pd["id"],
                platform=Platform.MASTODON,
                author=pd["author"],
                author_display_name=pd["author_display_name"],
                content=pd["content"],
                urls=pd["urls"],
                created_at=datetime.fromisoformat(pd["created_at"]),
                is_boost=pd["is_boost"],
                original_post_id=pd.get("original_post_id"),
                boosted_by=pd.get("boosted_by"),
                boost_count=pd.get("boost_count", 0),
                like_count=pd.get("like_count", 0),
            )
            for pd in cached
        ]

    fetcher = MastodonFetcher(
        instance_url=settings.mastodon.instance_url,
        access_token=settings.mastodon.access_token,
    )

    posts = await fetcher.fetch_timeline(
        timeline_type=TimelineType.HOME, cutoff=cutoff
    )

    cache.set_feed(
        "mastodon",
        "home",
        [
            {
                "id": p.id,
                "author": p.author,
                "author_display_name": p.author_display_name,
                "content": p.content,
                "urls": p.urls,
                "created_at": p.created_at.isoformat(),
                "is_boost": p.is_boost,
                "original_post_id": p.original_post_id,
                "boosted_by": p.boosted_by,
                "boost_count": p.boost_count,
                "like_count": p.like_count,
            }
            for p in posts
        ],
    )

    return posts


async def _fetch_bluesky_posts(
    settings: LinkgnomeSettings,
    cache: FeedCache,
    cutoff: datetime | None = None,
) -> list[Post]:
    """Fetch posts from Bluesky, checking cache first."""
    cached = cache.get_feed("bluesky", "home")
    if cached is not None:
        return [
            Post(
                id=pd["id"],
                platform=Platform.BLUESKY,
                author=pd["author"],
                author_display_name=pd["author_display_name"],
                content=pd["content"],
                urls=pd["urls"],
                created_at=datetime.fromisoformat(pd["created_at"]),
                is_boost=pd["is_boost"],
                original_post_id=pd.get("original_post_id"),
                boosted_by=pd.get("boosted_by"),
                boost_count=pd.get("boost_count", 0),
                like_count=pd.get("like_count", 0),
            )
            for pd in cached
        ]

    fetcher = BlueskyFetcher(
        handle=settings.bluesky.handle,
        app_password=settings.bluesky.app_password,
    )

    posts = await fetcher.fetch_timeline(timeline_type=TimelineType.HOME, limit=40)

    cache.set_feed(
        "bluesky",
        "home",
        [
            {
                "id": p.id,
                "author": p.author,
                "author_display_name": p.author_display_name,
                "content": p.content,
                "urls": p.urls,
                "created_at": p.created_at.isoformat(),
                "is_boost": p.is_boost,
                "original_post_id": p.original_post_id,
                "boosted_by": p.boosted_by,
                "boost_count": p.boost_count,
                "like_count": p.like_count,
            }
            for p in posts
        ],
    )

    return posts


def _display_links_page(
    scored_links: list[ScoredLink],
    page: int = 1,
    page_size: int = 42,
) -> None:
    """Display a page of scored links in a rich table."""
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_links = scored_links[start_idx:end_idx]

    if not page_links:
        console.print("[yellow]No links to display on this page.[/yellow]")
        console.print(
            f"[dim](Total available: {len(scored_links)}, "
            f"requested page: {page}, page size: {page_size})[/dim]"
        )
        return

    total_pages = max(1, (len(scored_links) - 1) // page_size + 1)
    table = Table(
        title=f"[bold]LinkGnome[/bold] - Page {page} of {total_pages}",
        show_header=True,
        header_style="bold cyan",
        box=None,
        expand=True,
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("P", width=3)
    table.add_column("Score", style="bold yellow", width=5)
    table.add_column("Link", style="bright_white")
    table.add_column("From", style="dim", width=28)

    for idx, link in enumerate(page_links, start=start_idx + 1):
        platform_icons = _get_platform_icons(link)
        score_str = f"{link.score:.1f}"

        display_url = _truncate_url(link.url)
        from_str = _get_from_display(link)

        table.add_row(
            str(idx),
            platform_icons,
            score_str,
            f"[link={link.url}]{display_url}[/link]",
            from_str,
        )

    console.print(table)
    console.print("")
    total_posts = sum(
        link.post_count + link.boost_count + link.like_count for link in scored_links
    )
    console.print(
        f"[dim]Total: {len(scored_links)} links | Engagements: {total_posts}[/dim]"
    )
    console.print("")


def _get_platform_icons(scored_link: ScoredLink) -> str:
    """Get platform icons for a scored link."""
    if not scored_link.source_platforms:
        return ""

    icons = []
    if Platform.MASTODON in scored_link.source_platforms:
        icons.append(PLATFORM_ICON[Platform.MASTODON])
    if Platform.BLUESKY in scored_link.source_platforms:
        icons.append(PLATFORM_ICON[Platform.BLUESKY])

    return " ".join(icons)


def _truncate_url(url: str, max_length: int = 35) -> str:
    """Truncate a URL for display."""
    if len(url) <= max_length:
        return url
    return url[: max_length - 3] + "…"


def _get_from_display(scored_link: ScoredLink, max_length: int = 28) -> str:
    """Get the 'From' display text showing authors."""
    authors = []
    if scored_link.posts:
        seen = set()
        for post in scored_link.posts:
            name = post.author_display_name or post.author
            if name not in seen:
                seen.add(name)
                authors.append(name)
        if len(authors) > 3:
            authors = authors[:3]
            authors.append(f"+{len(seen) - 3} more")

    from_str = ", ".join(authors)
    if len(from_str) > max_length:
        from_str = from_str[: max_length - 3] + "…"

    return from_str if from_str else "—"
