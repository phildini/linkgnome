"""Tests for Bluesky auth helpers."""
import respx
from django.test import TestCase

from accounts.bluesky import verify_credentials


@respx.mock
class VerifyCredentialsTest(TestCase):
    def test_verify_success(self):
        respx.post("https://bsky.social/xrpc/com.atproto.server.createSession").respond(
            200, json={
                "accessJwt": "jwt_token",
                "did": "did:plc:test123",
                "handle": "user.bsky.social",
            }
        )
        result = verify_credentials("user.bsky.social", "app_password")
        assert result["did"] == "did:plc:test123"
        assert result["handle"] == "user.bsky.social"

    def test_verify_fails(self):
        respx.post("https://bsky.social/xrpc/com.atproto.server.createSession").respond(
            401, json={"error": "Invalid credentials"}
        )
        with self.assertRaises(Exception):
            verify_credentials("bad_user", "wrong_password")
