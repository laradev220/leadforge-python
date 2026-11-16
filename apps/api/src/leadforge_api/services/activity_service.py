"""Live engine activity for the UI dock."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from leadforge_config import get_redis_client
from leadforge_database.models import Business, EnrichmentRun, EnrichmentStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.tenancy import user_business_ids

QUEUE_NAMES = (
    "discovery",
    "website",
    "contact",
    "social",
    "verification",
    "scoring",
    "export",
)


def _row(run: EnrichmentRun, business_name: str | None) -> dict[str, Any]:
    duration_ms = None
    if run.started_at and run.completed_at:
        duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)
    return {
        "id": str(run.id),
        "business_id": str(run.business_id),
        "business_name": business_name,
        "worker": run.worker_name,
        "status": run.status.value,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_ms": duration_ms,
        "error": run.error_message,
        "job_id": (run.metadata_ or {}).get("job_id"),
    }


async def activity(
    session: AsyncSession, user_id: UUID, *, recent_limit: int = 25
) -> dict[str, Any]:
    scope = Business.id.in_(user_business_ids(user_id))

    active_stmt = (
        select(EnrichmentRun, Business.name)
        .join(Business, Business.id == EnrichmentRun.business_id)
        .where(scope, EnrichmentRun.status == EnrichmentStatus.RUNNING)
        .order_by(EnrichmentRun.started_at.desc())
        .limit(50)
    )
    recent_stmt = (
        select(EnrichmentRun, Business.name)
        .join(Business, Business.id == EnrichmentRun.business_id)
        .where(
            scope,
            EnrichmentRun.status.in_([EnrichmentStatus.COMPLETED, EnrichmentStatus.FAILED]),
        )
        .order_by(EnrichmentRun.completed_at.desc())
        .limit(recent_limit)
    )

    active = [_row(run, name) for run, name in (await session.execute(active_stmt)).all()]
    recent = [_row(run, name) for run, name in (await session.execute(recent_stmt)).all()]

    queues: dict[str, int] = {}
    try:
        client = get_redis_client()
        try:
            for name in QUEUE_NAMES:
                queues[name] = int(await client.zcard(name) or 0)
        finally:
            await client.aclose()
    except Exception:
        queues = {}

    return {
        "active": active,
        "recent": recent,
        "queues": queues,
        "counts": {
            "active": len(active),
            "waiting": sum(queues.values()),
        },
    }
