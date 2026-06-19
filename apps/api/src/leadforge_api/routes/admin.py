"""Admin routes (queue stats, retry)."""

from __future__ import annotations

from fastapi import APIRouter

from leadforge_api.core.deps import AdminUser
from leadforge_api.core.response import success
from leadforge_api.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/queues", response_model=None)
async def queue_stats(_admin: AdminUser) -> dict:
    return success({"stats": await admin_service.get_queue_stats()})


@router.post("/queues/retry", response_model=None)
async def retry_failed(_admin: AdminUser) -> dict:
    count = await admin_service.retry_failed()
    return success({"retried": count})
