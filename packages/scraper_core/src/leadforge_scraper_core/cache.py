"""RedisHTMLCache — caches fetched HTML pages for 24 hours.

Key format: cache:html:{url_hash}:{user_agent_hash}
Respects Cache-Control: no-cache.
Invalidates when selector fails repeatedly (force fresh scrape).
"""

from __future__ import annotations

import hashlib
from typing import Any

import redis.asyncio as redis
from leadforge_config import get_settings


class RedisHTMLCache:
    """Redis-backed HTML page cache with configurable TTL and invalidation."""

    _PREFIX = "cache:html"
    _DEFAULT_TTL = 86400  # 24 hours

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        ttl_seconds: int = _DEFAULT_TTL,
    ) -> None:
        self._client = redis_client
        self._ttl = ttl_seconds

    async def _get_client(self) -> redis.Redis:
        if self._client:
            return self._client
        settings = get_settings()
        return redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=False,  # we store bytes
        )

    def _make_key(self, url: str, user_agent: str) -> str:
        """Create a deterministic cache key."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:32]
        ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:16]
        return f"{self._PREFIX}:{url_hash}:{ua_hash}"

    async def get(self, url: str, user_agent: str) -> bytes | None:
        """Return cached HTML bytes if present, None if not cached or no-cache header detected."""
        try:
            client = await self._get_client()
            key = self._make_key(url, user_agent)

            # Check for no-cache marker
            no_cache_key = f"{key}:no_cache"
            if await client.exists(no_cache_key):
                await client.aclose()
                return None

            data = await client.get(key)
            await client.aclose()
            return data
        except Exception:
            return None

    async def set(self, url: str, user_agent: str, html: bytes | str) -> None:
        """Cache HTML bytes with TTL."""
        try:
            client = await self._get_client()
            key = self._make_key(url, user_agent)
            if isinstance(html, str):
                html = html.encode("utf-8")
            await client.set(key, html, ex=self._ttl)
            # Clear any no-cache marker
            await client.delete(f"{key}:no_cache")
            await client.aclose()
        except Exception:
            pass

    async def invalidate(self, url: str, user_agent: str | None = None) -> None:
        """Force invalidate a cached page (optionally filtered by user_agent)."""
        try:
            client = await self._get_client()
            if user_agent:
                key = self._make_key(url, user_agent)
                await client.delete(key)
            else:
                pattern = f"{self._PREFIX}:*"
                cursor = 0
                while True:
                    cursor, batch = await client.scan(cursor, match=pattern, count=100)
                    for k in batch:
                        if k.startswith(f"{self._PREFIX}:{url}"):
                            await client.delete(k)
                    if cursor == 0:
                        break
            await client.aclose()
        except Exception:
            pass

    async def mark_no_cache(self, url: str, user_agent: str) -> None:
        """Mark a URL as explicitly no-cache for this user agent."""
        try:
            client = await self._get_client()
            key = self._make_key(url, user_agent)
            await client.set(f"{key}:no_cache", "1", ex=300)  # 5-minute no-cache marker
            await client.aclose()
        except Exception:
            pass

    async def get_or_fetch(
        self,
        url: str,
        user_agent: str,
        fetch_fn: Any,
        *,
        force_refresh: bool = False,
    ) -> str | None:
        """Get from cache or call fetch_fn to get fresh HTML.

        Args:
            url: URL to fetch.
            user_agent: User agent string (part of cache key).
            fetch_fn: Async callable that returns HTML string.
            force_refresh: If True, skip cache and fetch fresh.
        """
        if not force_refresh:
            cached = await self.get(url, user_agent)
            if cached:
                try:
                    return cached.decode("utf-8")
                except UnicodeDecodeError:
                    pass

        html = await fetch_fn(url)
        if html:
            await self.set(url, user_agent, html)
        return html

    async def stats(self) -> dict[str, Any]:
        """Return cache statistics (hits, misses, size)."""
        try:
            client = await self._get_client()
            keys = []
            cursor = 0
            while True:
                cursor, batch = await client.scan(cursor, match=f"{self._PREFIX}:*", count=1000)
                keys.extend(batch)
                if cursor == 0:
                    break

            total_keys = len(keys)
            # Estimate memory (rough)
            ttl_values = await client.mget(keys[:100]) if keys else []
            avg_size = sum(len(v or b"") for v in ttl_values) / max(len(ttl_values), 1)
            estimated_bytes = int(avg_size * total_keys)

            await client.aclose()
            return {
                "total_keys": total_keys,
                "estimated_bytes": estimated_bytes,
                "ttl_seconds": self._ttl,
            }
        except Exception:
            return {"error": "failed to retrieve stats"}


# Global cache instance
_cache: RedisHTMLCache | None = None


def get_cache() -> RedisHTMLCache:
    global _cache
    if _cache is None:
        _cache = RedisHTMLCache()
    return _cache
