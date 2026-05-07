"""Interactive setup wizard for LinkGnome."""

from __future__ import annotations

import asyncio
import webbrowser

import questionary
from rich.console import Console

from linkgnome.config import ConfigManager
from linkgnome.fetchers.mastodon import MastodonFetcher

console = Console()


def run_setup(config_manager: ConfigManager) -> None:
    """Run the interactive setup wizard."""
    console.print("\n[bold cyan]" + "=" * 60)
    console.print("[bold cyan]  Welcome to LinkGnome Setup Wizard!")
    console.print("[bold cyan]" + "=" * 60 + "\n")

    settings = config_manager.get()

    setup_mastodon = questionary.confirm(
        "Configure Mastodon?",
        default=not settings.mastodon.enabled,
    ).ask()

    if setup_mastodon:
        _setup_mastodon(settings, config_manager)

    setup_bluesky = questionary.confirm(
        "Configure Bluesky? (optional, can be done later)",
        default=settings.bluesky.enabled,
    ).ask()

    if setup_bluesky:
        _setup_bluesky(settings, config_manager)

    period_result = questionary.text(
        "Default time period for feeds (e.g., 24h, 7d):",
        default=f"{settings.period_hours}h",
    ).ask()

    if period_result:
        settings.period_hours = _parse_period_hours(period_result.strip())

    config_manager.save(settings)

    console.print("\n[bold green]\N{CHECK MARK} Configuration saved![/bold green]")
    console.print(f"  Config file: [dim]{config_manager.config_path}[/dim]\n")


def _setup_mastodon(settings: object, config_manager: ConfigManager) -> None:
    """Set up Mastodon authentication."""
    console.print("\n[bold]Setting up Mastodon...[/bold]\n")

    if settings.mastodon.enabled:
        console.print(f"Current instance: {settings.mastodon.instance_url}")
        change = questionary.confirm("Change Mastodon configuration?").ask()
        if not change:
            return

    instance_url = questionary.text(
        "Mastodon instance URL (e.g., mastodon.social):",
        default=_extract_domain(settings.mastodon.instance_url)
        if settings.mastodon.instance_url
        else "",
    ).ask()

    if not instance_url:
        console.print("[yellow]Skipping Mastodon setup.[/yellow]")
        return

    if not instance_url.startswith("http"):
        instance_url = f"https://{instance_url}"

    console.print("\nRegistering OAuth application...")

    try:
        fetcher = MastodonFetcher(instance_url)
        registration = asyncio.run(fetcher.register_app())

        settings.mastodon.instance_url = instance_url
        settings.mastodon.client_id = registration["client_id"]
        settings.mastodon.client_secret = registration["client_secret"]

        auth_url = fetcher.get_auth_url(registration["client_id"], instance_url)

        console.print("\n[bold]Opening browser for authorization...[/bold]")
        console.print(f"If the browser doesn't open, visit:\n  {auth_url}\n")

        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

        auth_code = questionary.text(
            "Enter the authorization code from the browser:",
        ).ask()

        if not auth_code:
            console.print(
                "[yellow]No auth code entered. Mastodon not configured.[/yellow]"
            )
            return

        console.print("\nExchanging authorization code for access token...")
        token_response = asyncio.run(
            fetcher.get_access_token(
                registration["client_id"],
                registration["client_secret"],
                auth_code.strip(),
                instance_url,
            )
        )

        settings.mastodon.access_token = token_response["access_token"]
        settings.mastodon.enabled = True

        console.print("[green]\N{CHECK MARK} Mastodon configured successfully![/green]")

    except Exception as e:
        console.print(f"[red]\N{CROSS MARK} Failed to configure Mastodon: {e}[/red]")
        settings.mastodon.instance_url = instance_url


def _setup_bluesky(settings: object, config_manager: ConfigManager) -> None:
    """Set up Bluesky authentication."""
    console.print("\n[bold]Setting up Bluesky...[/bold]\n")

    if settings.bluesky.enabled:
        console.print(f"Current handle: {settings.bluesky.handle}")
        change = questionary.confirm("Change Bluesky configuration?").ask()
        if not change:
            return

    handle = questionary.text(
        "Bluesky handle (e.g., user.bsky.social):",
        default=settings.bluesky.handle if settings.bluesky.handle else "",
    ).ask()

    if not handle:
        console.print("[yellow]Skipping Bluesky setup.[/yellow]")
        return

    app_password = questionary.password(
        "App password (create one at https://bsky.app/settings/app-passwords):",
    ).ask()

    if not app_password:
        console.print(
            "[yellow]No app password entered. Bluesky not configured.[/yellow]"
        )
        return

    console.print("\nVerifying Bluesky credentials...")

    try:
        from linkgnome.fetchers.bluesky import BlueskyFetcher

        fetcher = BlueskyFetcher(handle, app_password)
        asyncio.run(fetcher.verify_credentials())

        settings.bluesky.handle = handle
        settings.bluesky.app_password = app_password
        settings.bluesky.enabled = True

        console.print("[green]\N{CHECK MARK} Bluesky configured successfully![/green]")

    except Exception as e:
        console.print(
            f"[red]\N{CROSS MARK} Failed to verify Bluesky credentials: {e}[/red]"
        )


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ""
    url = url.replace("https://", "").replace("http://", "")
    return url.split("/")[0]


def _parse_period_hours(period_str: str) -> int:
    """Parse period string into hours."""
    period_str = period_str.lower()
    if period_str.endswith("h"):
        return max(1, int(period_str[:-1]))
    elif period_str.endswith("d"):
        return max(1, int(period_str[:-1]) * 24)
    else:
        return max(1, int(period_str))
