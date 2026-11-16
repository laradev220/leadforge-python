"""Search job routes. Mirrors apps/api/src/routes/search-jobs.ts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.pagination import get_pagination
from leadforge_api.core.response import paginated, success
from leadforge_api.schemas import (
    CreateSearchJobRequest,
    CreateSearchJobResponse,
    SearchJobResponse,
    SearchJobStatus,
)
from leadforge_api.services import search_job_service

router = APIRouter(prefix="/search-jobs", tags=["search-jobs"])


def _parse_search_job_status(value: str) -> SearchJobStatus:
    """Parse a status string into SearchJobStatus, returning a 422 on invalid values."""
    try:
        return SearchJobStatus(value.upper())
    except ValueError:
        valid = [s.value for s in SearchJobStatus]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"Invalid status '{value}'. Must be one of: {', '.join(valid)}",
            },
        )


@router.post("", response_model=None)
async def create_search_job(
    body: CreateSearchJobRequest, user_id: CurrentUserId, session: DBSession
) -> dict:
    job = await search_job_service.create(
        session,
        user_id,
        body.keyword,
        body.location,
        body.radius_km,
        country=body.country,
    )
    return success(
        CreateSearchJobResponse(job_id=job.id, status=SearchJobStatus(job.status)).model_dump(
            mode="json"
        )
    )


@router.get("", response_model=None)
async def list_search_jobs(
    user_id: CurrentUserId,
    session: DBSession,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
) -> dict:
    pagination = get_pagination({"page": str(page), "limit": str(limit)})
    status_filter = _parse_search_job_status(status) if status else None
    jobs, total = await search_job_service.list_for_user(
        session, user_id, pagination.page, pagination.limit, status_filter
    )
    return paginated(
        [SearchJobResponse.model_validate(j).model_dump(mode="json") for j in jobs],
        total,
        pagination.page,
        pagination.limit,
    )


@router.get("/{job_id}/progress", response_model=None)
async def job_progress(job_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    from uuid import UUID

    return success(await search_job_service.progress(session, user_id, UUID(job_id)))


@router.get("/{job_id}", response_model=None)
async def get_search_job(job_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    from uuid import UUID

    job = await search_job_service.get_by_id(session, user_id, UUID(job_id))
    return success(SearchJobResponse.model_validate(job).model_dump(mode="json"))


@router.post("/{job_id}/cancel", response_model=None)
async def cancel_search_job(job_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    from uuid import UUID

    await search_job_service.cancel(session, user_id, UUID(job_id))
    return success({"cancelled": True})
