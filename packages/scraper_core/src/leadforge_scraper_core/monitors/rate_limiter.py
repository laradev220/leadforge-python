"""Rate limiting — global concurrency semaphore and per-domain request delays."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from leadforge_config import get_settings


class GlobalConcurrencyLimiter:
    """Limits concurrent scraping requests across all sources."""

    def __init__(self, max_concurrent: int | None = None) -> None:
        settings = get_settings()
        self._semaphore = asyncio.Semaphore(max_concurrent or settings.scraper_concurrency)

    async def __aenter__(self) -> None:
        await self._semaphore.acquire()

    async def __aexit__(self, *args: Any) -> None:
        self._semaphore.release()

    @property
    def available(self) -> int:
        """Number of available concurrent slots (approximate)."""
        return self._semaphore._value  # type: ignore[attr-defined]


class DomainRateLimiter:
    """Enforces minimum delay between requests to the same domain.

    Tracks per-domain last-request timestamps and ensures at least
    *delay_seconds* have elapsed before the next request to that domain.

    The lock only protects the shared timestamp dictionary to avoid head-of-line
    blocking across unrelated domains — the per-domain wait happens outside
    the critical section.
    """

    def __init__(self, delay_seconds: float = 1.0) -> None:
        self._delay = delay_seconds
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, domain: str) -> None:
        """Wait until enough time has passed since the last request to *domain*."""
        # Read last-request time under the lock, but calculate wait outside
        async with self._lock:
            last = self._last_request.get(domain, 0.0)

        elapsed = time.monotonic() - last
        if elapsed < self._delay:
            wait = self._delay - elapsed
            await asyncio.sleep(wait)

        # Update timestamp under the lock after the wait
        async with self._lock:
            self._last_request[domain] = time.monotonic()

    async def reset(self, domain: str) -> None:
        """Reset the rate limit for a domain (e.g., after a circuit opens)."""
        async with self._lock:
            self._last_request.pop(domain, None)

    async def wait_for(self, domain: str) -> None:
        """Alias for acquire — wait until rate limit window has passed."""
        await self.acquire(domain)

    @property
    def domains(self) -> list[str]:
        return list(self._last_request.keys())


class AdaptiveRateLimiter:
    """Wraps DomainRateLimiter with automatic back-off on 429 responses.

    When a 429 is detected for a domain, the delay is doubled (up to max_delay)
    and a penalty is applied for the configured penalty_duration_seconds.
    """

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        penalty_duration: float = 300.0,
    ) -> None:
        self._domain_limiter = DomainRateLimiter(delay_seconds=base_delay)
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._penalty_duration = penalty_duration
        self._penalty_until: dict[str, float] = {}
        self._current_delay: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, domain: str) -> None:
        """Wait if rate-limited or penalty is active."""
        penalty = self._penalty_until.get(domain, 0.0)
        if penalty > time.monotonic():
            wait = penalty - time.monotonic()
            await asyncio.sleep(wait)

        # Use adapted delay from back-off, or base delay
        delay = self._current_delay.get(domain, self._base_delay)
        # Apply the adapted delay to the domain limiter for this call
        original_delay = self._domain_limiter._delay
        self._domain_limiter._delay = delay
        try:
            await self._domain_limiter.acquire(domain)
        finally:
            # Restore original delay so other domains aren't affected
            self._domain_limiter._delay = original_delay
        # Reset to base delay after successful request
        async with self._lock:
            self._current_delay[domain] = self._base_delay

    async def note_429(self, domain: str) -> None:
        """Double the delay for a domain after a 429 response."""
        async with self._lock:
            current = self._current_delay.get(domain, self._base_delay)
            new_delay = min(current * 2, self._max_delay)
            self._current_delay[domain] = new_delay
            self._penalty_until[domain] = time.monotonic() + self._penalty_duration
            import structlog

            log = structlog.get_logger("scraper.rate_limiter")
            log.warning(
                "rate_limit.backoff",
                domain=domain,
                new_delay=new_delay,
            )

    @property
    def domains(self) -> list[str]:
        return self._domain_limiter.domains

    async def reset(self, domain: str) -> None:
        """Reset the rate limit for a domain (e.g., after a circuit opens)."""
        await self._domain_limiter.reset(domain)
