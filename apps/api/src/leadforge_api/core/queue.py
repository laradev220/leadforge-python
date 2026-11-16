"""Arq client (producer side). Used by API to enqueue jobs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from arq.connections import ArqRedis, RedisSettings, create_pool
from leadforge_config import get_settings
from leadforge_worker_core.core import verification_job_id

_pool: ArqRedis | None = None


def _settings() -> RedisSettings:
    s = get_settings()
    return RedisSettings(host=s.redis_host, port=s.redis_port, password=s.redis_password or None)


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(_settings())
    return _pool


async def enqueue(queue_name: str, job_name: str, payload: dict[str, Any]) -> None:
    pool = await get_pool()
    await pool.enqueue_job(job_name, _queue_name=queue_name, **payload)


async def enqueue_discovery(search_job_id: UUID, country: str | None = None) -> None:
    payload: dict[str, str] = {"search_job_id": str(search_job_id)}
    if country:
        payload["country"] = country
    await enqueue("discovery", "discovery", payload)


async def enqueue_website(business_id: UUID) -> None:
    await enqueue("website", "website", {"business_id": str(business_id)})


async def enqueue_contact(business_id: UUID, website_url: str) -> None:
    await enqueue(
        "contact",
        "contact",
        {"business_id": str(business_id), "website_url": website_url},
    )


async def enqueue_social(business_id: UUID, website_url: str) -> None:
    await enqueue(
        "social",
        "social",
        {"business_id": str(business_id), "website_url": website_url},
    )


async def enqueue_scoring(business_id: UUID) -> None:
    await enqueue("scoring", "scoring", {"business_id": str(business_id)})


async def enqueue_verification(business_id: UUID, force: bool = False) -> None:
    pool = await get_pool()
    await pool.enqueue_job(
        "verification",
        _queue_name="verification",
        _job_id=verification_job_id(str(business_id)),
        business_id=str(business_id),
        force=force,
    )


async def enqueue_export(export_id: UUID, filters: dict | None = None) -> None:
    payload: dict[str, Any] = {"export_id": str(export_id)}
    if filters:
        payload["filters"] = filters
    await enqueue("export", "export", payload)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
