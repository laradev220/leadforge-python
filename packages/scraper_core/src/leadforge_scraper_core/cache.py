"""RedisHTMLCache — caches fetched HTML pages for 24 hours.

Key format: cache:html:{url_hash}:{user_agent_hash}
Respects Cache-Control: no-cache.
Invalidates when selector fails repeatedly (force fresh scrape).
"""

from __future__ import annotations

import hashlib
from typing import Any

import redis.asyncio as redis
from leadforge_config import get_redis_client


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
        self._owns_client = redis_client is None
        self._ttl = ttl_seconds

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = get_redis_client()
        return self._client

    async def close(self) -> None:
        """Close the owned connection (no-op for injected clients)."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def _url_hash(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:32]

    def _make_key(self, url: str, user_agent: str) -> str:
        """Create a deterministic cache key."""
        ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:16]
        return f"{self._PREFIX}:{self._url_hash(url)}:{ua_hash}"

    async def get(self, url: str, user_agent: str) -> bytes | None:
        """Return cached HTML bytes if present, None if not cached or no-cache requested."""
        try:
            client = self._get_client()
            key = self._make_key(url, user_agent)

            if await client.exists(f"{key}:no_cache"):
                return None

            return await client.get(key)
        except Exception:
            return None

    async def set(self, url: str, user_agent: str, html: bytes | str) -> None:
        """Cache HTML bytes with TTL."""
        try:
            client = self._get_client()
            key = self._make_key(url, user_agent)
            if isinstance(html, str):
                html = html.encode("utf-8")
            await client.set(key, html, ex=self._ttl)
            # Clear any no-cache marker
            await client.delete(f"{key}:no_cache")
        except Exception:
            pass

    async def invalidate(self, url: str, user_agent: str | None = None) -> None:
        """Force invalidate a cached page (optionally filtered by user_agent)."""
        try:
            client = self._get_client()
            if user_agent:
                await client.delete(self._make_key(url, user_agent))
                return

            # Keys are hashed, so match on the URL-hash component.
            pattern = f"{self._PREFIX}:{self._url_hash(url)}:*"
            cursor = 0
            while True:
                cursor, batch = await client.scan(cursor, match=pattern, count=100)
                if batch:
                    await client.delete(*batch)
                if cursor == 0:
                    break
        except Exception:
            pass

    async def mark_no_cache(self, url: str, user_agent: str) -> None:
        """Mark a URL as explicitly no-cache for this user agent."""
        try:
            client = self._get_client()
            key = self._make_key(url, user_agent)
            await client.set(f"{key}:no_cache", "1", ex=300)  # 5-minute marker
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
        """Get from cache or call fetch_fn to get fresh HTML."""
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
        """Return cache statistics (estimated size, key count)."""
        try:
            client = self._get_client()
            keys: list[bytes] = []
            cursor = 0
            while True:
                cursor, batch = await client.scan(cursor, match=f"{self._PREFIX}:*", count=1000)
                keys.extend(batch)
                if cursor == 0:
                    break

            total_keys = len(keys)
            sample = keys[:100]
            values = await client.mget(sample) if sample else []
            avg_size = sum(len(v or b"") for v in values) / max(len(values), 1)
            return {
                "total_keys": total_keys,
                "estimated_bytes": int(avg_size * total_keys),
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
