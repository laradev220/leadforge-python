"""Scheduler worker: turns due search schedules into jobs.

Runs as a polling process (not an arq consumer). Due rows are locked with
FOR UPDATE SKIP LOCKED so multiple schedulers never double-run a schedule.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from datetime import UTC, datetime

import structlog
from leadforge_config import get_settings
from leadforge_database import get_session_ctx
from leadforge_database.models import SearchJob, SearchJobStatus, SearchSchedule
from leadforge_shared.scheduling import compute_next_run
from leadforge_worker_core.core import enqueue_job
from sqlalchemy import select

logger = structlog.get_logger("scheduler")


async def tick_once() -> int:
    now = datetime.now(UTC)
    created: list[tuple[str, str | None]] = []

    async with get_session_ctx() as session:
        result = await session.execute(
            select(SearchSchedule)
            .where(SearchSchedule.enabled.is_(True), SearchSchedule.next_run_at <= now)
            .order_by(SearchSchedule.next_run_at)
            .limit(20)
            .with_for_update(skip_locked=True)
        )
        schedules = list(result.scalars().all())

        for schedule in schedules:
            job = SearchJob(
                user_id=schedule.user_id,
                schedule_id=schedule.id,
                keyword=schedule.keyword,
                location=schedule.location,
                radius_km=schedule.radius_km,
                status=SearchJobStatus.PENDING,
            )
            session.add(job)
            await session.flush()
            schedule.last_run_at = now
            schedule.last_job_id = job.id
            schedule.next_run_at = compute_next_run(
                now=now,
                cadence=schedule.cadence,
                hour=schedule.hour,
                minute=schedule.minute,
                weekday=schedule.weekday,
                day_of_month=schedule.day_of_month,
                tz_name=schedule.timezone,
            )
            created.append((str(job.id), schedule.country))

        await session.commit()

    for job_id, country in created:
        payload = {"search_job_id": job_id}
        if country:
            payload["country"] = country
        await enqueue_job("discovery", "discovery", payload)

    if created:
        logger.info("schedules_dispatched", count=len(created))
    return len(created)


async def scheduler_loop() -> None:
    settings = get_settings()
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # pragma: no cover
            loop.add_signal_handler(sig, stop.set)

    logger.info("scheduler_started", poll_seconds=settings.schedule_poll_seconds)
    while not stop.is_set():
        try:
            await tick_once()
        except Exception as exc:
            logger.error("scheduler_tick_failed", error=str(exc))
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.schedule_poll_seconds)
    logger.info("scheduler_stopped")


def main() -> None:
    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
