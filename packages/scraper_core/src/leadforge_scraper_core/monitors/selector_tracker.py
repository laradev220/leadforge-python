"""SelectorTracker — records success/failure per selector and detects degradation.

Tracks selectors in Redis so all workers share the same view of selector health.
When a selector fails 3 times in a row it is marked deprecated and a warning is logged.

Usage:
    tracker = SelectorTracker()
    await tracker.record_success("yelp", "name", "a[href*='/biz/']")
    await tracker.record_failure("yelp", "name", "a[href*='/biz/']")
    is_deprecated = await tracker.is_deprecated("yelp", "name", "a[href*='/biz/']")
"""

from __future__ import annotations

import os
import time
from typing import Any

import redis.asyncio as redis

from leadforge_config import get_settings
from leadforge_scraper_core.cache import get_cache


class SelectorTracker:
    """Tracks selector health in Redis with failure streak detection."""

    # Redis key prefix
    _PREFIX = "scraper:selectors"

    # How many consecutive failures before marking deprecated
    _FAILURE_THRESHOLD = 3

    # TTL for selector records (24 hours)
    _TTL_SECONDS = 86400

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._client = redis_client
        self._cache = get_cache()  # wired to cache invalidation on deprecation

    async def _get_client(self) -> redis.Redis:
        if self._client:
            return self._client
        settings = get_settings()
        return redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )

    def _key(self, source: str, field: str, selector: str) -> str:
        """Redis key for a specific selector's stats."""
        # Normalise selector for key (slashes etc. are fine in redis keys)
        safe_sel = selector.replace(" ", "_").replace("/", "_")
        return f"{self._PREFIX}:{source}:{field}:{safe_sel}"

    def _stats_key(self, source: str, field: str) -> str:
        """Redis hash key storing {selector: "successes,failures,streak"}."""
        return f"{self._PREFIX}:stats:{source}:{field}"

    async def record_success(
        self,
        source: str,
        field: str,
        selector: str,
        *,
        url: str | None = None,
    ) -> None:
        """Record a successful extraction with this selector."""
        try:
            client = await self._get_client()
            stats_key = self._stats_key(source, field)

            # Get current stats
            stats_raw = await client.hget(stats_key, selector)
            successes, failures, streak = self._parse_stats(stats_raw)

            successes += 1
            streak = max(0, streak - 1) if streak > 0 else 0  # reset negative streak on success

            await client.hset(stats_key, selector, f"{successes},{failures},{streak}")
            await client.expire(stats_key, self._TTL_SECONDS)
            await client.aclose()
        except Exception:
            pass

    async def record_failure(
        self,
        source: str,
        field: str,
        selector: str,
        *,
        url: str | None = None,
    ) -> None:
        """Record a failed extraction attempt with this selector.

        If the failure streak reaches _FAILURE_THRESHOLD, the selector is
        marked deprecated and a warning is emitted (for alerting system).
        """
        try:
            client = await self._get_client()
            stats_key = self._stats_key(source, field)

            stats_raw = await client.hget(stats_key, selector)
            successes, failures, streak = self._parse_stats(stats_raw)

            failures += 1
            streak += 1

            await client.hset(stats_key, selector, f"{successes},{failures},{streak}")
            await client.expire(stats_key, self._TTL_SECONDS)

            # Check threshold
            if streak >= self._FAILURE_THRESHOLD:
                await self._mark_deprecated(client, source, field, selector, url=url)
                import structlog
                log = structlog.get_logger("scraper.selector_tracker")
                log.warning(
                    "selector.deprecated",
                    source=source,
                    field=field,
                    selector=selector,
                    streak=streak,
                    url=url,
                )

            await client.aclose()
        except Exception:
            pass

    async def _mark_deprecated(
        self,
        client: redis.Redis,
        source: str,
        field: str,
        selector: str,
        url: str | None = None,
    ) -> None:
        """Mark a selector as deprecated in Redis and invalidate its cache entry."""
        deprecated_key = f"{self._PREFIX}:deprecated:{source}:{field}"
        await client.hset(deprecated_key, selector, int(time.time()))
        await client.expire(deprecated_key, self._TTL_SECONDS * 7)  # 1 week TTL

        # Invalidate cache so the next retry gets fresh HTML with working selectors
        if url:
            await self._cache.invalidate(url)
            import structlog
            log = structlog.get_logger("scraper.selector_tracker")
            log.info("selector.cache_invalidated", url=url, source=source, field=field)

    async def is_deprecated(
        self,
        source: str,
        field: str,
        selector: str,
    ) -> bool:
        """Return True if this selector is currently marked deprecated."""
        try:
            client = await self._get_client()
            deprecated_key = f"{self._PREFIX}:deprecated:{source}:{field}"
            val = await client.hget(deprecated_key, selector)
            await client.aclose()
            return val is not None
        except Exception:
            return False

    async def get_best_selector(
        self,
        source: str,
        field: str,
        candidates: list[str],
    ) -> str | None:
        """Return the first non-deprecated selector from candidates, sorted by success rate."""
        try:
            client = await self._get_client()
            stats_key = self._stats_key(source, field)

            # Filter out deprecated
            valid = [s for s in candidates if not await self.is_deprecated(source, field, s)]
            if not valid:
                return candidates[0] if candidates else None

            # Pick the one with highest success ratio
            best = None
            best_ratio = -1.0
            for sel in valid:
                raw = await client.hget(stats_key, sel)
                s, f, _ = self._parse_stats(raw)
                total = s + f
                if total > 0:
                    ratio = s / total
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best = sel

            await client.aclose()
            return best or valid[0]
        except Exception:
            return candidates[0] if candidates else None

    @staticmethod
    def _parse_stats(raw: str | None) -> tuple[int, int, int]:
        """Parse 'successes,failures,streak' string into ints."""
        if not raw:
            return 0, 0, 0
        parts = raw.split(",")
        try:
            return int(parts[0]), int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            return 0, 0, 0