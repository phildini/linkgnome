"""Bluesky auth helpers for the webapp."""
import httpx


BSKY_ATPROTO = "https://bsky.social"


def verify_credentials(handle: str, app_password: str) -> dict:
    """Verify Bluesky credentials and return session info."""
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{BSKY_ATPROTO}/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": app_password},
        )
        response.raise_for_status()
        return response.json()
