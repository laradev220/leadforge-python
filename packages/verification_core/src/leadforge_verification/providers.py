"""Email verifiers.

`mx` (default) proves the domain accepts mail and is deliberately reported as
RISKY, never VALID: mailbox-level checks arrive with the SMTP/provider
adapters in a later slice.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

import dns.asyncresolver
import dns.exception
import dns.resolver
from leadforge_shared.types import VerificationStatus

from leadforge_verification.types import VerificationResult, result

MxLookup = Callable[[str, int], Awaitable[bool | None]]


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
