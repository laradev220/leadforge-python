"""Redis client factory.

Every Redis connection in the codebase must go through this helper so the
``REDIS_PASSWORD`` setting is applied consistently. Clients built ad-hoc with
``redis.Redis(host=..., port=...)`` silently fail with ``NOAUTH`` once auth is
enabled.
"""

from __future__ import annotations

import redis.asyncio as redis

from leadforge_config.settings import get_settings


def get_redis_client(*, decode_responses: bool = False) -> redis.Redis:
    """Build an async Redis client from settings (host, port, password)."""
    settings = get_settings()
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        decode_responses=decode_responses,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
