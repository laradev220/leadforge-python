"""Scraper health, metrics, and cache management routes."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Response
from leadforge_scraper_core.cache import get_cache
from leadforge_scraper_core.metrics import (
    get_metrics_bytes,
    get_metrics_content_type,
    get_scraper_health,
)

from leadforge_api.core.deps import AdminUser

router = APIRouter(prefix="/scrapers", tags=["scrapers"])


@router.get("/health")
async def scraper_health() -> dict[str, Any]:
    """Return health status of all scraper sources.

    Shows circuit breaker state, recent failure rate, and last scrape time
    for each registered source.
    """
    health = await get_scraper_health()
    return {
        "success": True,
        "service": "leadforge-scrapers",
        "timestamp": time.time(),
        "sources": health,
    }


@router.get("/metrics")
async def scraper_metrics() -> Response:
    """Prometheus metrics endpoint for all scraper instrumentation."""
    return Response(
        content=get_metrics_bytes(),
        media_type=get_metrics_content_type(),
    )


@router.get("/cache/stats")
async def cache_stats(_admin: AdminUser) -> dict[str, Any]:
    """Return HTML cache statistics (key count, estimated size). Admin only."""
    cache = get_cache()
    stats = await cache.stats()
    return {"success": True, "cache": stats}


@router.post("/cache/invalidate")
async def cache_invalidate(
    _admin: AdminUser,
    url: str,
    user_agent: str = "default",
) -> dict[str, Any]:
    """Force invalidate a cached page (e.g., after selector degradation). Admin only."""
    # _admin: AdminUser is a FastAPI dependency injected via Depends(require_admin)
    cache = get_cache()
    await cache.invalidate(url, user_agent)
    return {"success": True, "invalidated": True}


@router.post("/cache/clear")
async def cache_clear(_admin: AdminUser) -> dict[str, Any]:
    """Clear the entire HTML cache (admin only)."""
    get_cache()
    try:
        import redis.asyncio as redis
        from leadforge_config import get_settings

        settings = get_settings()
        client = redis.Redis(host=settings.redis_host, port=settings.redis_port)
        keys = []
        cursor = 0
        while True:
            cursor, batch = await client.scan(cursor, match="cache:html:*", count=1000)
            keys.extend(batch)
            if cursor == 0:
                break
        if keys:
            await client.delete(*keys)
        await client.aclose()
        return {"success": True, "keys_deleted": len(keys)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.get("/selectors/{source}")
async def get_selector_stats(
    source: str,
    _admin: AdminUser,
) -> dict[str, Any]:
    """Return selector health stats for a source. Admin only."""
    # _admin: AdminUser is a FastAPI dependency injected via Depends(require_admin)
    from leadforge_scraper_core.monitors.selector_tracker import SelectorTracker

    SelectorTracker()
    # We return a placeholder — actual implementation would need Redis inspection
    return {
        "success": True,
        "source": source,
        "note": "Selector stats available via SelectorTracker.get_best_selector()",
    }
