"""CLI entry point for LinkGnome."""

from __future__ import annotations

import click
from rich.console import Console

from linkgnome.config import ConfigManager
from linkgnome.setup import run_setup
from linkgnome.tui import run_tui

console = Console()


@click.group()
@click.pass_context
def main(ctx: click.Context) -> None:
    """LinkGnome - Terminal-based link aggregator for social feeds."""
    ctx.ensure_object(dict)
    ctx.obj["config_manager"] = ConfigManager()


@main.command()
@click.pass_context
def setup(ctx: click.Context) -> None:
    """Walk through interactive configuration."""
    config_manager = ctx.obj["config_manager"]
    run_setup(config_manager)


@main.command()
@click.option("--period", type=str, default=None, help="Time period (e.g., 24h, 7d)")
@click.option("--page", type=int, default=1, help="Page number (42 items per page)")
@click.option(
    "--platform",
    type=click.Choice(["mastodon", "bluesky"]),
    default=None,
    help="Filter by platform",
)
@click.pass_context
def fetch(
    ctx: click.Context, period: str | None, page: int, platform: str | None
) -> None:
    """Fetch and display ranked links from your feeds."""
    config_manager = ctx.obj["config_manager"]
    settings = config_manager.get()

    if not settings.mastodon.enabled and not settings.bluesky.enabled:
        console.print(
            "[bold yellow]No platforms configured. Run 'linkgnome setup' first.[/bold yellow]"
        )
        raise click.Abort()

    hours = _parse_period(period) if period else settings.period_hours
    run_tui(settings, hours=hours, page=page, platform_filter=platform)


@main.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Show current configuration."""
    config_manager = ctx.obj["config_manager"]
    settings = config_manager.get()

    console.print("[bold]LinkGnome Configuration[/bold]\n")

    console.print("[bold]Mastodon:[/bold]")
    if settings.mastodon.enabled:
        console.print(f"  Instance: {settings.mastodon.instance_url}")
        console.print("  Status: [green]Configured[/green]")
    else:
        console.print("  Status: [red]Not configured[/red]")

    console.print("\n[bold]Bluesky:[/bold]")
    if settings.bluesky.enabled:
        console.print(f"  Handle: {settings.bluesky.handle}")
        console.print("  Status: [green]Configured[/green]")
    else:
        console.print("  Status: [red]Not configured[/red]")

    console.print("\n[bold]Settings:[/bold]")
    console.print(f"  Period: {settings.period_hours} hours")
    console.print(f"  Page size: {settings.page_size} items")


def _parse_period(period_str: str) -> int:
    """Parse period string like '24h' or '7d' into hours."""
    period_str = period_str.strip().lower()
    if period_str.endswith("h"):
        return int(period_str[:-1])
    elif period_str.endswith("d"):
        return int(period_str[:-1]) * 24
    else:
        return int(period_str)


if __name__ == "__main__":
    main()
