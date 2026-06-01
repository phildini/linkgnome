"""Mastodon OAuth helpers for the webapp."""
import httpx

from accounts.models import InstanceApp


MASTODON_SCOPES = "read:accounts read:statuses"


def register_instance_app(instance_url: str, callback_url: str) -> dict:
    """Register a LinkGnome app with a Mastodon instance and cache credentials."""
    cached = InstanceApp.objects.filter(instance_url=instance_url).first()
    if cached:
        return {"client_id": cached.client_id, "client_secret": cached.client_secret}

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{instance_url}/api/v1/apps",
            data={
                "client_name": "LinkGnome",
                "redirect_uris": callback_url,
                "scopes": MASTODON_SCOPES,
                "website": "https://github.com/phildini/linkgnome",
            },
        )
        response.raise_for_status()
        data = response.json()

    InstanceApp.objects.create(
        instance_url=instance_url,
        client_id=data["client_id"],
        client_secret=data["client_secret"],
    )
    return {"client_id": data["client_id"], "client_secret": data["client_secret"]}


def build_authorize_url(instance_url: str, client_id: str, callback_url: str) -> str:
    """Build the OAuth authorization URL to redirect the user to."""
    from urllib.parse import urlencode

    params = urlencode({
        "client_id": client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": MASTODON_SCOPES,
        "force_login": "true",
    })
    return f"{instance_url}/oauth/authorize?{params}"


def exchange_code(
    instance_url: str, client_id: str, client_secret: str, code: str, callback_url: str
) -> dict:
    """Exchange an authorization code for an access token."""
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{instance_url}/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": callback_url,
                "scope": MASTODON_SCOPES,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


def fetch_identity(instance_url: str, access_token: str) -> dict:
    """Fetch the authenticated user's Mastodon identity."""
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{instance_url}/api/v1/accounts/verify_credentials",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
