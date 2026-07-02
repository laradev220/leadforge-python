"""Search job service. Mirrors apps/api/src/services/search-job-service.ts."""

from __future__ import annotations

from uuid import UUID

from leadforge_database.models import SearchJob, SearchJobStatus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.errors import not_found
from leadforge_api.core.queue import enqueue_discovery


async def create(
    session: AsyncSession,
    user_id: UUID,
    keyword: str,
    location: str,
    radius_km: int | None,
    country: str | None = None,
) -> SearchJob:
    job = SearchJob(
        user_id=user_id,
        keyword=keyword,
        location=location,
        radius_km=radius_km,
        status=SearchJobStatus.PENDING,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    await enqueue_discovery(job.id, country=country)
    return job


async def list_for_user(
    session: AsyncSession, user_id: UUID, page: int, limit: int, status_filter: str | None
) -> tuple[list[SearchJob], int]:
    where = [SearchJob.user_id == user_id]
    if status_filter:
        where.append(SearchJob.status == status_filter)

    total = await session.scalar(select(func.count()).select_from(SearchJob).where(*where))
    result = await session.execute(
        select(SearchJob)
        .where(*where)
        .order_by(SearchJob.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return list(result.scalars()), int(total or 0)


async def get_by_id(session: AsyncSession, user_id: UUID, job_id: UUID) -> SearchJob:
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(SearchJob)
        .options(
            selectinload(SearchJob.businesses).selectinload(
                __import__(
                    "leadforge_database.models", fromlist=["SearchJobBusiness"]
                ).SearchJobBusiness.business
            )
        )
        .where(SearchJob.id == job_id, SearchJob.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise not_found("Search job not found")
    return job


async def cancel(session: AsyncSession, user_id: UUID, job_id: UUID) -> None:
    result = await session.execute(
        select(SearchJob).where(SearchJob.id == job_id, SearchJob.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise not_found("Search job not found")

    job.status = SearchJobStatus.CANCELLED
    await session.commit()
