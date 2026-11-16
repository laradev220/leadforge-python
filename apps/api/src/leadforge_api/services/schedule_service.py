"""Recurring search schedules."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from leadforge_database.models import ScheduleCadence, SearchJob, SearchSchedule
from leadforge_shared.scheduling import compute_next_run
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.errors import bad_request, not_found
from leadforge_api.services import search_job_service


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[SearchSchedule]:
    result = await session.execute(
        select(SearchSchedule)
        .where(SearchSchedule.user_id == user_id)
        .order_by(SearchSchedule.created_at.desc())
    )
    return list(result.scalars())


async def _get(session: AsyncSession, user_id: UUID, schedule_id: UUID) -> SearchSchedule:
    schedule = (
        await session.execute(
            select(SearchSchedule).where(
                SearchSchedule.id == schedule_id, SearchSchedule.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if schedule is None:
        raise not_found("Schedule not found")
    return schedule


def _next_run(schedule: SearchSchedule, now: datetime | None = None) -> datetime:
    return compute_next_run(
        now=now or datetime.now(UTC),
        cadence=schedule.cadence,
        hour=schedule.hour,
        minute=schedule.minute,
        weekday=schedule.weekday,
        day_of_month=schedule.day_of_month,
        tz_name=schedule.timezone,
    )


async def create(session: AsyncSession, user_id: UUID, data) -> SearchSchedule:
    schedule = SearchSchedule(
        user_id=user_id,
        keyword=data.keyword,
        location=data.location,
        country=data.country.upper() if data.country else None,
        radius_km=data.radius_km,
        cadence=data.cadence,
        hour=data.hour,
        minute=data.minute,
        weekday=data.weekday,
        day_of_month=data.day_of_month,
        timezone=data.timezone,
        enabled=data.enabled,
        next_run_at=datetime.now(UTC),
    )
    schedule.next_run_at = _next_run(schedule)
    session.add(schedule)
    await session.commit()
    await session.refresh(schedule)
    return schedule


async def update(session: AsyncSession, user_id: UUID, schedule_id: UUID, data) -> SearchSchedule:
    schedule = await _get(session, user_id, schedule_id)
    for field in (
        "keyword",
        "location",
        "radius_km",
        "hour",
        "minute",
        "weekday",
        "day_of_month",
        "timezone",
        "enabled",
    ):
        value = getattr(data, field, None)
        if value is not None:
            setattr(schedule, field, value)
    if data.country is not None:
        schedule.country = data.country.upper()
    if data.cadence is not None:
        schedule.cadence = data.cadence

    if schedule.cadence == ScheduleCadence.WEEKLY and schedule.weekday is None:
        raise bad_request("weekday is required for weekly schedules")
    schedule.next_run_at = _next_run(schedule)
    await session.commit()
    await session.refresh(schedule)
    return schedule


async def delete(session: AsyncSession, user_id: UUID, schedule_id: UUID) -> None:
    schedule = await _get(session, user_id, schedule_id)
    await session.delete(schedule)
    await session.commit()


async def run_now(session: AsyncSession, user_id: UUID, schedule_id: UUID) -> SearchJob:
    schedule = await _get(session, user_id, schedule_id)
    job = await search_job_service.create(
        session,
        user_id,
        schedule.keyword,
        schedule.location,
        schedule.radius_km,
        country=schedule.country,
    )
    job.schedule_id = schedule.id
    schedule.last_run_at = datetime.now(UTC)
    schedule.last_job_id = job.id
    await session.commit()
    await session.refresh(job)
    return job


async def runs(
    session: AsyncSession, user_id: UUID, schedule_id: UUID, limit: int = 10
) -> list[SearchJob]:
    await _get(session, user_id, schedule_id)
    result = await session.execute(
        select(SearchJob)
        .where(SearchJob.schedule_id == schedule_id, SearchJob.user_id == user_id)
        .order_by(SearchJob.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())
