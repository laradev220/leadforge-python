"""CRM / Sheets integration routes."""

from __future__ import annotations

from fastapi import APIRouter
from leadforge_shared.types import IntegrationKind

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.response import success
from leadforge_api.schemas import (
    IntegrationPushRequest,
    IntegrationPushResponse,
    IntegrationResponse,
    IntegrationTestResponse,
    IntegrationUpsertRequest,
)
from leadforge_api.services import integration_service

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=None)
async def list_integrations(user_id: CurrentUserId, session: DBSession) -> dict:
    return success(await integration_service.list_for_user(session, user_id))


@router.put("/{kind}", response_model=None)
async def upsert_integration(
    kind: IntegrationKind,
    body: IntegrationUpsertRequest,
    user_id: CurrentUserId,
    session: DBSession,
) -> dict:
    row = await integration_service.upsert(session, user_id, kind, body.config, body.enabled)
    return success(IntegrationResponse.model_validate(row).model_dump(mode="json"))


@router.delete("/{kind}", response_model=None)
async def delete_integration(
    kind: IntegrationKind, user_id: CurrentUserId, session: DBSession
) -> dict:
    await integration_service.remove(session, user_id, kind)
    return success({"deleted": True})


@router.post("/{kind}/test", response_model=None)
async def test_integration(
    kind: IntegrationKind, user_id: CurrentUserId, session: DBSession
) -> dict:
    result = await integration_service.test(session, user_id, kind)
    return success(IntegrationTestResponse(**result).model_dump(mode="json"))


@router.post("/{kind}/push", response_model=None)
async def push_integration(
    kind: IntegrationKind,
    body: IntegrationPushRequest,
    user_id: CurrentUserId,
    session: DBSession,
) -> dict:
    result = await integration_service.push(session, user_id, kind, body, body.limit)
    return success(IntegrationPushResponse(**result).model_dump(mode="json"))
