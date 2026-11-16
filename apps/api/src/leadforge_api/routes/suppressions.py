"""Suppression list routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.response import success
from leadforge_api.schemas import (
    SuppressionBulkRequest,
    SuppressionCreateRequest,
    SuppressionResponse,
)
from leadforge_api.services import suppression_service

router = APIRouter(prefix="/suppressions", tags=["suppressions"])


@router.get("", response_model=None)
async def list_suppressions(user_id: CurrentUserId, session: DBSession) -> dict:
    rows = await suppression_service.list_for_user(session, user_id)
    return success(
        [SuppressionResponse.model_validate(row).model_dump(mode="json") for row in rows]
    )


@router.post("", response_model=None, status_code=201)
async def add_suppression(
    body: SuppressionCreateRequest, user_id: CurrentUserId, session: DBSession
) -> dict:
    entry = await suppression_service.add(
        session, user_id, body.kind, body.value, body.reason, body.note
    )
    return success(SuppressionResponse.model_validate(entry).model_dump(mode="json"))


@router.post("/bulk", response_model=None)
async def bulk_suppressions(
    body: SuppressionBulkRequest, user_id: CurrentUserId, session: DBSession
) -> dict:
    entries = [entry.model_dump() for entry in body.entries]
    added, skipped = await suppression_service.bulk_add(session, user_id, entries)
    return success({"added": added, "skipped": skipped})


@router.delete("/{suppression_id}", response_model=None)
async def delete_suppression(
    suppression_id: str, user_id: CurrentUserId, session: DBSession
) -> dict:
    await suppression_service.remove(session, user_id, UUID(suppression_id))
    return success({"deleted": True})
