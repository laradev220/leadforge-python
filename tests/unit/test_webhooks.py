"""Webhook signing, SSRF validation, and schemas."""

from __future__ import annotations

import pytest
from leadforge_api.schemas import WebhookCreateRequest
from leadforge_shared.net import validate_public_https_url
from leadforge_webhook_worker.main import sign
from pydantic import ValidationError


class TestSigning:
    def test_signature_is_deterministic(self) -> None:
        body = b'{"event":"export.completed"}'
        first = sign("secret", 1700000000, body)
        second = sign("secret", 1700000000, body)
        assert first == second
        assert len(first) == 64

    def test_signature_changes_with_body(self) -> None:
        assert sign("secret", 1700000000, b"a") != sign("secret", 1700000000, b"b")

    def test_signature_changes_with_secret(self) -> None:
        assert sign("a", 1700000000, b"x") != sign("b", 1700000000, b"x")


class TestSsrf:
    async def test_http_rejected(self) -> None:
        with pytest.raises(ValueError, match="https"):
            await validate_public_https_url("http://example.com/hook")

    async def test_localhost_rejected(self) -> None:
        with pytest.raises(ValueError, match="host"):
            await validate_public_https_url("https://localhost/hook")

    async def test_private_ip_rejected(self) -> None:
        with pytest.raises(ValueError, match="private"):
            await validate_public_https_url("https://127.0.0.1/hook")


class TestWebhookSchema:
    def test_unknown_event_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WebhookCreateRequest(url="https://example.com/hook", events=["nope.event"])

    def test_valid_events(self) -> None:
        body = WebhookCreateRequest(
            url="https://example.com/hook",
            events=["export.completed", "search.completed"],
        )
        assert len(body.events) == 2
