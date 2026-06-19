"""Admin / queue stats service."""

from __future__ import annotations

import redis.asyncio as redis

from leadforge_config import get_settings

_QUEUE_NAMES = ("discovery", "website", "contact", "social", "scoring", "export")


async def get_queue_stats() -> dict[str, dict[str, int]]:
    settings = get_settings()
    client = redis.Redis(host=settings.redis_host, port=settings.redis_port)
    try:
        stats: dict[str, dict[str, int]] = {}
        for name in _QUEUE_NAMES:
            counts = {
                "waiting": int(await client.llen(f"arq:queue:{name}")),
                "in_progress": int(await client.zcard(f"arq:in-progress:{name}") or 0),
                "complete": int(await client.zcard(f"arq:result:{name}") or 0),
                "failed": int(await client.zcard(f"arq:failed:{name}") or 0),
            }
            stats[name] = counts
        return stats
    finally:
        await client.aclose()


async def retry_failed() -> int:
    """Move failed jobs back to waiting for all queues. Returns retried count."""
    settings = get_settings()
    client = redis.Redis(host=settings.redis_host, port=settings.redis_port)
    total = 0
    try:
        for name in _QUEUE_NAMES:
            failed_key = f"arq:failed:{name}"
            members = await client.zrange(failed_key, 0, -1)
            if not members:
                continue
            pipe = client.pipeline()
            for job_id in members:
                pipe.lpush(f"arq:queue:{name}", job_id)
                pipe.zrem(failed_key, job_id)
            await pipe.execute()
            total += len(members)
        return total
    finally:
        await client.aclose()
