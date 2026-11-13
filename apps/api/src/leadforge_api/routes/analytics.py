"""Analytics routes."""

from __future__ import annotations

from fastapi import APIRouter

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.response import success
from leadforge_api.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=None)
async def dashboard(user_id: CurrentUserId, session: DBSession) -> dict:
    return success(await analytics_service.dashboard_stats(session, user_id))


@router.get("/lead-distribution", response_model=None)
async def lead_distribution(user_id: CurrentUserId, session: DBSession) -> dict:
    return success({"distribution": await analytics_service.lead_distribution(session, user_id)})
