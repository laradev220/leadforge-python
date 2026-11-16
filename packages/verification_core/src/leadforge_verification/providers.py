"""Email verifiers.

`mx` (default) proves the domain accepts mail and is deliberately reported as
RISKY, never VALID: mailbox-level checks arrive with the SMTP/provider
adapters in a later slice.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx
from leadforge_shared.types import VerificationStatus

from leadforge_verification.types import VerificationResult, result

MxLookup = Callable[[str, int], Awaitable[bool | None]]
MxHostLookup = Callable[[str, int], Awaitable[str | None]]
SmtpProbe = Callable[[str, int, str, str], Awaitable[int | None]]
HttpGet = Callable[[str, dict[str, str]], Awaitable[dict[str, Any]]]


async def _dns_mx_lookup(domain: str, timeout_ms: int) -> bool | None:
    """True when MX records exist, False when they do not, None on failure."""
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = timeout_ms / 1000.0
    resolver.timeout = timeout_ms / 1000.0
    try:
        answers = await resolver.resolve(domain, "MX")
        return bool(answers)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False
    except (dns.exception.DNSException, OSError):
        return None


@runtime_checkable
class EmailVerifier(Protocol):
    async def verify(self, value: str) -> VerificationResult: ...


async def _dns_mx_host(domain: str, timeout_ms: int) -> str | None:
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = timeout_ms / 1000.0
    resolver.timeout = timeout_ms / 1000.0
    try:
        answers = await resolver.resolve(domain, "MX")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return None
    except (dns.exception.DNSException, OSError):
        return None
    hosts = sorted(
        ((int(r.preference), str(r.exchange).rstrip(".")) for r in answers),
        key=lambda item: item[0],
    )
    return hosts[0][1] if hosts else None


class MxEmailVerifier:
    """Domain-level check: MX present -> RISKY, missing -> INVALID."""

    method = "mx"

    def __init__(
        self,
        *,
        timeout_ms: int = 10_000,
        cache_ttl_s: int = 3600,
        lookup: MxLookup | None = None,
    ) -> None:
        self._timeout_ms = timeout_ms
        self._cache_ttl_s = cache_ttl_s
        self._lookup: MxLookup = lookup or _dns_mx_lookup
        self._cache: dict[str, tuple[bool | None, float]] = {}

    async def _mx_exists(self, domain: str) -> bool | None:
        now = time.monotonic()
        cached = self._cache.get(domain)
        if cached is not None and now - cached[1] < self._cache_ttl_s:
            return cached[0]
        exists = await self._lookup(domain, self._timeout_ms)
        self._cache[domain] = (exists, now)
        return exists

    async def verify(self, value: str) -> VerificationResult:
        domain = value.rsplit("@", 1)[-1].strip().lower()
        exists = await self._mx_exists(domain)
        if exists is None:
            return result(
                VerificationStatus.UNKNOWN,
                confidence=0,
                reason="dns_error",
                method=self.method,
            )
        if exists:
            return result(
                VerificationStatus.RISKY,
                confidence=60,
                reason="mx_present",
                method=self.method,
            )
        return result(
            VerificationStatus.INVALID,
            confidence=0,
            reason="mx_missing",
            method=self.method,
        )


async def _smtp_probe(host: str, timeout_ms: int, helo: str, recipient: str) -> int | None:
    """RCPT probe: returns the SMTP reply code, or None if unreachable."""
    timeout = timeout_ms / 1000.0

    async def read_reply(reader: asyncio.StreamReader) -> int | None:
        line = await asyncio.wait_for(reader.readline(), timeout)
        if not line:
            return None
        text = line.decode(errors="replace").strip()
        code = int(text[:3]) if text[:3].isdigit() else None
        while len(text) > 3 and text[3] == "-":
            line = await asyncio.wait_for(reader.readline(), timeout)
            text = line.decode(errors="replace").strip()
        return code

    writer = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, 25), timeout)
        if await read_reply(reader) != 220:
            return None
        for command in (
            f"EHLO {helo}\r\n",
            f"MAIL FROM:<verify@{helo}>\r\n",
        ):
            writer.write(command.encode())
            await writer.drain()
            if (await read_reply(reader) or 0) // 100 != 2:
                return None
        writer.write(f"RCPT TO:<{recipient}>\r\n".encode())
        await writer.drain()
        return await read_reply(reader)
    except Exception:
        return None
    finally:
        if writer is not None:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


class SmtpEmailVerifier:
    """Mailbox check over SMTP RCPT (no DATA). Falls back to RISKY."""

    method = "smtp"

    def __init__(
        self,
        *,
        timeout_ms: int = 10_000,
        helo_domain: str = "leadforge.dev",
        host_lookup: MxHostLookup | None = None,
        probe: SmtpProbe | None = None,
    ) -> None:
        self._timeout_ms = timeout_ms
        self._helo = helo_domain
        self._host_lookup = host_lookup or _dns_mx_host
        self._probe = probe or _smtp_probe

    async def verify(self, value: str) -> VerificationResult:
        domain = value.rsplit("@", 1)[-1].strip().lower()
        host = await self._host_lookup(domain, self._timeout_ms)
        if host is None:
            return result(
                VerificationStatus.INVALID,
                confidence=0,
                reason="mx_missing",
                method=self.method,
            )
        code = await self._probe(host, self._timeout_ms, self._helo, value)
        if code is None:
            return result(
                VerificationStatus.RISKY,
                confidence=60,
                reason="smtp_unreachable",
                method=self.method,
            )
        if code in (250, 251):
            return result(
                VerificationStatus.VALID,
                confidence=90,
                reason=f"smtp_{code}",
                method=self.method,
            )
        if code in (550, 551, 553, 554):
            return result(
                VerificationStatus.INVALID,
                confidence=0,
                reason=f"smtp_{code}",
                method=self.method,
            )
        return result(
            VerificationStatus.UNKNOWN,
            confidence=0,
            reason=f"smtp_{code}",
            method=self.method,
        )


async def _http_get(url: str, params: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


_ZEROBOUNCE_STATUS = {
    "valid": (VerificationStatus.VALID, 95),
    "catch-all": (VerificationStatus.CATCH_ALL, 60),
    "invalid": (VerificationStatus.INVALID, 0),
    "spamtrap": (VerificationStatus.INVALID, 0),
    "abuse": (VerificationStatus.INVALID, 0),
    "do_not_mail": (VerificationStatus.UNKNOWN, 0),
    "unknown": (VerificationStatus.UNKNOWN, 0),
}


class ZeroBounceVerifier:
    method = "provider:zerobounce"

    def __init__(
        self,
        *,
        api_key: str,
        timeout_ms: int = 10_000,
        http_get: HttpGet | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout_ms = timeout_ms
        self._get = http_get or _http_get

    async def verify(self, value: str) -> VerificationResult:
        if not self._api_key:
            return result(
                VerificationStatus.UNKNOWN,
                confidence=0,
                reason="provider_missing_key",
                method=self.method,
            )
        try:
            payload = await self._get(
                "https://api.zerobounce.net/v2/validate",
                {"api_key": self._api_key, "email": value},
            )
        except Exception:
            return result(
                VerificationStatus.UNKNOWN,
                confidence=0,
                reason="provider_error",
                method=self.method,
            )
        raw = str(payload.get("status", "")).lower().replace(" ", "-")
        status, confidence = _ZEROBOUNCE_STATUS.get(raw, (VerificationStatus.UNKNOWN, 0))
        return result(
            status,
            confidence=confidence,
            reason=f"zerobounce:{raw or 'unknown'}",
            method=self.method,
        )
