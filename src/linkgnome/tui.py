"""Terminal UI for displaying ranked links."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from linkgnome.db import LinkgnomeDB
from linkgnome.config import LinkgnomeSettings
from linkgnome.fetchers.base import Platform, Post, TimelineType
from linkgnome.fetchers.bluesky import BlueskyFetcher
from linkgnome.fetchers.mastodon import MastodonFetcher
from linkgnome.scorer import ScoredLink, score_links

console = Console()

PLATFORM_COLOR = {
    Platform.MASTODON: "magenta",
    Platform.BLUESKY: "blue",
}


def run_tui(
    settings: LinkgnomeSettings,
    hours: int = 24,
    page: int = 1,
    page_size: int = 10,
    platform_filter: str | None = None,
) -> None:
    """Run the terminal UI to display ranked links."""
    console.print("\n[cyan bold]Fetching links from your feeds...[/cyan bold]")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    db = LinkgnomeDB()
    # Schema is created lazily on first call to conn
    _ = db.conn

    try:
        posts = _fetch_all_posts(settings, db, platform_filter, cutoff)
    except Exception as e:
        console.print(f"[red]Error fetching feeds: {e}[/red]")
        return

    if not posts:
        console.print("[yellow]No posts found in the specified time period.[/yellow]")
        return

    console.print(f"[dim]Fetched {len(posts)} posts, scoring links...[/dim]")

    scored_links = asyncio.run(score_links(posts, period_hours=hours, db=db))

    if not scored_links:
        console.print("[yellow]No links found in the specified time period.[/yellow]")
        return

    db.close()
    _display_links_page(scored_links, page, page_size)


def _fetch_all_posts(
    settings: LinkgnomeSettings,
    db: LinkgnomeDB,
    platform_filter: str | None = None,
    cutoff: datetime | None = None,
) -> list[Post]:
    """Fetch posts from both platforms."""
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
            tasks.append(_fetch_mastodon_posts(settings, db, cutoff))
        if bluesky_enabled:
            tasks.append(_fetch_bluesky_posts(settings, db, cutoff))
        results = await asyncio.gather(*tasks)
        for result_list in results:
            posts.extend(result_list)

    asyncio.run(_fetch_both())
    return posts


async def _fetch_mastodon_posts(
    settings: LinkgnomeSettings,
    db: LinkgnomeDB,
    cutoff: datetime | None = None,
) -> list[Post]:
    """Fetch posts from Mastodon with pagination, save to DB."""
    if cutoff:
        recent_posts = db.load_posts(platform="mastodon", since=cutoff)
        if recent_posts:
            return recent_posts

    db.clear_old_posts(keep_hours=24)

    fetcher = MastodonFetcher(
        instance_url=settings.mastodon.instance_url,
        access_token=settings.mastodon.access_token,
    )

    posts = await fetcher.fetch_timeline(
        timeline_type=TimelineType.HOME, cutoff=cutoff
    )

    db.save_posts(posts)

    return posts


async def _fetch_bluesky_posts(
    settings: LinkgnomeSettings,
    db: LinkgnomeDB,
    cutoff: datetime | None = None,
) -> list[Post]:
    """Fetch posts from Bluesky, checking DB first."""
    if cutoff:
        recent_posts = db.load_posts(platform="bluesky", since=cutoff)
        if recent_posts:
            return recent_posts

    db.clear_old_posts(keep_hours=24)

    fetcher = BlueskyFetcher(
        handle=settings.bluesky.handle,
        app_password=settings.bluesky.app_password,
    )

    await fetcher.authenticate()

    posts = await fetcher.fetch_timeline(
        timeline_type=TimelineType.HOME, cutoff=cutoff
    )

    db.save_posts(posts)
    return posts


def _display_links_page(
    scored_links: list[ScoredLink],
    page: int = 1,
    page_size: int = 42,
) -> None:
    """Display a page of scored links as compact card rows."""
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

    console.print("")
    console.print(f"[cyan bold]LinkGnome[/cyan bold] — Page {page} of {total_pages}")
    console.print(f"[dim]{'━' * console.width}[/dim]")

    for idx, link in enumerate(page_links, start=start_idx + 1):
        text = Text()

        score_style = "bold yellow" if link.score >= 5.0 else "bold white"
        platform_parts = _get_platform_parts(link)

        text.append(f"{idx}.  ", style="dim")
        for color, char in platform_parts:
            text.append(f" {char} ", style=color)
        text.append(f"⬆ {link.score:.1f}  ", style=score_style)

        if link.title and link.title != link.url:
            text.append(f"{link.title}  ", style="bold")

        text.append(link.url, style="blue underline link " + link.url)
        text.append("\n")
        text.append(f"    by {_get_from_display(link)}", style="dim")
        post_url = _get_post_url(link)
        if post_url:
            text.append(" · ", style="dim")
            text.append(post_url, style="blue underline link " + post_url)

        panel = Panel(
            text,
            padding=(0, 1),
            border_style="dim",
            expand=True,
        )
        console.print(panel)

    console.print(f"[dim]{'━' * console.width}[/dim]")
    total_posts = sum(
        link.post_count + link.boost_count + link.like_count
        for link in scored_links
    )
    console.print(
        f"[dim]Total: {len(scored_links)} links | Engagements: {total_posts}[/dim]"
    )
    console.print("")


def _get_platform_parts(scored_link: ScoredLink) -> list[tuple[str, str]]:
    """Get styled platform parts."""
    parts = []
    if not scored_link.source_platforms:
        return parts
    if Platform.MASTODON in scored_link.source_platforms:
        parts.append(("magenta", "M"))
    if Platform.BLUESKY in scored_link.source_platforms:
        parts.append(("blue", "B"))
    return parts


def _get_from_display(scored_link: ScoredLink, max_length: int = 80) -> str:
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
        from_str = from_str[: max_length - 3] + "..."

    return from_str if from_str else "—"

def _get_post_url(scored_link: ScoredLink) -> str:
    """Get a displayable URL for the first post that shared this link."""
    if not scored_link.posts:
        return ""
    first_post = scored_link.posts[0]
    if not first_post.raw_data:
        return _construct_post_url_fallback(first_post)
    if first_post.platform == Platform.MASTODON:
        return first_post.raw_data.get("url") or first_post.raw_data.get("uri") or ""
    if first_post.platform == Platform.BLUESKY:
        return _bluesky_post_to_url(first_post.raw_data)
    return ""

def _construct_post_url_fallback(post: Post) -> str:
    """Construct post URL when raw_data is unavailable."""
    if post.platform == Platform.BLUESKY and post.id.startswith("at://"):
        return _bluesky_at_uri_to_url(post.id)
    return post.id

def _bluesky_post_to_url(raw_data: dict) -> str:
    """Convert Bluesky post raw data to bsky.app URL."""
    post = raw_data.get("post", {})
    uri = post.get("uri", "")
    author = post.get("author", {})
    handle = author.get("handle", "")
    if handle:
        parts = uri.split("/")
        rkey = parts[-1] if parts else ""
        return f"https://bsky.app/profile/{handle}/post/{rkey}"
    return _bluesky_at_uri_to_url(uri)

def _bluesky_at_uri_to_url(at_uri: str) -> str:
    """Convert Bluesky AT URI to bsky.app URL."""
    if not at_uri.startswith("at://"):
        return at_uri
    parts = at_uri[5:].split("/")
    if len(parts) >= 3 and parts[1] == "app.bsky.feed.post":
        did = parts[0]
        rkey = parts[2]
        return f"https://bsky.app/profile/{did}/post/{rkey}"
    return at_uri
