"""Redis-backed fixed-window rate limiting for unauthenticated endpoints."""

from __future__ import annotations

from fastapi import Request
from leadforge_config import get_redis_client

from leadforge_api.core.errors import AppError


async def enforce_rate_limit(
    request: Request,
    *,
    bucket: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Raise 429 when the caller exceeds ``limit`` requests per window.

    Fails open when Redis is unavailable: a cache outage must not lock every
    user out of authentication.
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"ratelimit:{bucket}:{client_ip}"
    try:
        client = get_redis_client()
        try:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, window_seconds)
            if int(count) > limit:
                raise AppError(
                    429,
                    "RATE_LIMITED",
                    "Too many attempts. Try again later.",
                    {"retry_after_seconds": window_seconds},
                )
        finally:
            await client.aclose()
    except AppError:
        raise
    except Exception:
        return
