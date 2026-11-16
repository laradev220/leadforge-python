"""Engine activity routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.response import success
from leadforge_api.services import activity_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/activity", response_model=None)
async def engine_activity(
    user_id: CurrentUserId,
    session: DBSession,
    recent_limit: int = Query(25, ge=1, le=100),
) -> dict:
    return success(await activity_service.activity(session, user_id, recent_limit=recent_limit))
