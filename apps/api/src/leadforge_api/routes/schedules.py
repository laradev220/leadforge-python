"""Scheduled search routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.response import success
from leadforge_api.schemas import (
    ScheduleCreateRequest,
    ScheduleResponse,
    ScheduleRunResponse,
    ScheduleUpdateRequest,
)
from leadforge_api.services import schedule_service

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=None)
async def list_schedules(user_id: CurrentUserId, session: DBSession) -> dict:
    rows = await schedule_service.list_for_user(session, user_id)
    return success([ScheduleResponse.model_validate(row).model_dump(mode="json") for row in rows])


@router.post("", response_model=None, status_code=201)
async def create_schedule(
    body: ScheduleCreateRequest, user_id: CurrentUserId, session: DBSession
) -> dict:
    row = await schedule_service.create(session, user_id, body)
    return success(ScheduleResponse.model_validate(row).model_dump(mode="json"))


@router.patch("/{schedule_id}", response_model=None)
async def update_schedule(
    schedule_id: str,
    body: ScheduleUpdateRequest,
    user_id: CurrentUserId,
    session: DBSession,
) -> dict:
    row = await schedule_service.update(session, user_id, UUID(schedule_id), body)
    return success(ScheduleResponse.model_validate(row).model_dump(mode="json"))


@router.delete("/{schedule_id}", response_model=None)
async def delete_schedule(schedule_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    await schedule_service.delete(session, user_id, UUID(schedule_id))
    return success({"deleted": True})


@router.post("/{schedule_id}/run", response_model=None, status_code=202)
async def run_schedule(schedule_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    job = await schedule_service.run_now(session, user_id, UUID(schedule_id))
    return success({"job_id": str(job.id)})


@router.get("/{schedule_id}/runs", response_model=None)
async def schedule_runs(
    schedule_id: str,
    user_id: CurrentUserId,
    session: DBSession,
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    jobs = await schedule_service.runs(session, user_id, UUID(schedule_id), limit)
    return success(
        [
            ScheduleRunResponse.model_validate(
                {
                    "job_id": job.id,
                    "status": job.status,
                    "keyword": job.keyword,
                    "location": job.location,
                    "total_discovered": job.total_discovered,
                    "total_enriched": job.total_enriched,
                    "created_at": job.created_at,
                }
            ).model_dump(mode="json")
            for job in jobs
        ]
    )
