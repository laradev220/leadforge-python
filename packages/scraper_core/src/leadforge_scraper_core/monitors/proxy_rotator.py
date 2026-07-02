"""ProxyManager — rotates through a list of proxies, marking bad ones for 1 hour.

Reads proxy list from PROXY_LIST env var (comma-separated).
Each proxy can optionally include auth: http://user:pass@host:port.
"""

from __future__ import annotations

import asyncio
import os

import redis.asyncio as redis
from leadforge_config import get_settings


class ProxyManager:
    """Cycles through proxies, tracks failures, skips bad ones for 1 hour."""

    # Redis key for bad proxy timestamps
    _BAD_PREFIX = "scraper:bad_proxy"
    _BAD_TTL = 3600  # 1 hour

    def __init__(self, proxies: list[str] | None = None) -> None:
        # Load from env if not provided
        if proxies is None:
            raw = os.environ.get("PROXY_LIST", "")
            proxies = [p.strip() for p in raw.split(",") if p.strip()]

        self._proxies = proxies or []
        self._index = 0
        self._lock = asyncio.Lock()
        self._failures: dict[str, int] = {}
        self._failure_threshold = 3

    def __len__(self) -> int:
        return len(self._proxies)

    @property
    def has_proxies(self) -> bool:
        return bool(self._proxies)

    async def get_next(self) -> str | None:
        """Return the next available proxy (or None if no proxies configured)."""
        if not self._proxies:
            return None

        async with self._lock:
            # Filter out bad proxies
            available = await self._filter_available()
            if not available:
                # All proxies are bad — reset and return first
                self._index = 0
                return self._proxies[0] if self._proxies else None

            # Round-robin through available proxies
            proxy = available[self._index % len(available)]
            self._index = (self._index + 1) % len(available)
            return proxy

    async def record_success(self, proxy: str) -> None:
        """Clear failure count for a proxy after a successful request."""
        async with self._lock:
            self._failures.pop(proxy, None)
            # Also clear from Redis bad list
            await self._mark_good(proxy)

    async def record_failure(self, proxy: str, exc: Exception | None = None) -> None:
        """Increment failure count and mark proxy bad after threshold is reached."""
        async with self._lock:
            count = self._failures.get(proxy, 0) + 1
            self._failures[proxy] = count

            if count >= self._failure_threshold:
                await self._mark_bad(proxy)
                import structlog

                log = structlog.get_logger("scraper.proxy_rotator")
                log.warning(
                    "proxy.marked_bad",
                    proxy=proxy,
                    failures=count,
                    error=str(exc) if exc else None,
                )

    async def get_proxy_for_url(self, url: str) -> str | None:
        """Return proxy appropriate for the given URL (mostly same logic)."""
        return await self.get_next()

    async def _filter_available(self) -> list[str]:
        """Return proxies that are not currently marked as bad in Redis."""
        if not self._proxies:
            return []

        try:
            settings = get_settings()
            client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                decode_responses=True,
            )
            available = []
            for proxy in self._proxies:
                is_bad = await client.exists(f"{self._BAD_PREFIX}:{self._hash_proxy(proxy)}")
                if not is_bad:
                    available.append(proxy)
            await client.aclose()
            return available if available else list(self._proxies)
        except Exception:
            return list(self._proxies)

    async def _mark_bad(self, proxy: str) -> None:
        """Mark a proxy as bad and schedule its removal.

        Writes to the same per-proxy hash key that _filter_available reads from.
        """
        try:
            settings = get_settings()
            client = redis.Redis(host=settings.redis_host, port=settings.redis_port)
            key = f"{self._BAD_PREFIX}:{self._hash_proxy(proxy)}"
            await client.set(key, "1", ex=self._BAD_TTL)
            await client.aclose()
        except Exception:
            pass

    async def _mark_good(self, proxy: str) -> None:
        try:
            settings = get_settings()
            client = redis.Redis(host=settings.redis_host, port=settings.redis_port)
            key = f"{self._BAD_PREFIX}:{self._hash_proxy(proxy)}"
            await client.delete(key)
            await client.aclose()
        except Exception:
            pass

    @staticmethod
    def _hash_proxy(proxy: str) -> str:
        """Deterministic hash for Redis key."""
        import hashlib

        return hashlib.sha256(proxy.encode()).hexdigest()[:16]


# Global proxy manager instance
_proxy_manager: ProxyManager | None = None


def get_proxy_manager() -> ProxyManager:
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    return _proxy_manager
