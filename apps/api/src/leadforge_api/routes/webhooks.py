"""Webhook management routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.response import success
from leadforge_api.schemas import (
    WebhookCreateRequest,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookUpdateRequest,
)
from leadforge_api.services import webhook_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("", response_model=None)
async def list_webhooks(user_id: CurrentUserId, session: DBSession) -> dict:
    rows = await webhook_service.list_for_user(session, user_id)
    return success([WebhookResponse.model_validate(row).model_dump(mode="json") for row in rows])


@router.post("", response_model=None, status_code=201)
async def create_webhook(
    body: WebhookCreateRequest, user_id: CurrentUserId, session: DBSession
) -> dict:
    row = await webhook_service.create(session, user_id, body.url, body.events)
    return success(WebhookResponse.model_validate(row).model_dump(mode="json"))


@router.patch("/{endpoint_id}", response_model=None)
async def update_webhook(
    endpoint_id: str,
    body: WebhookUpdateRequest,
    user_id: CurrentUserId,
    session: DBSession,
) -> dict:
    row = await webhook_service.update(session, user_id, UUID(endpoint_id), body)
    return success(WebhookResponse.model_validate(row).model_dump(mode="json"))


@router.delete("/{endpoint_id}", response_model=None)
async def delete_webhook(endpoint_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    await webhook_service.delete(session, user_id, UUID(endpoint_id))
    return success({"deleted": True})


@router.post("/{endpoint_id}/rotate-secret", response_model=None)
async def rotate_secret(endpoint_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    row = await webhook_service.rotate_secret(session, user_id, UUID(endpoint_id))
    return success(WebhookResponse.model_validate(row).model_dump(mode="json"))


@router.get("/{endpoint_id}/deliveries", response_model=None)
async def list_deliveries(
    endpoint_id: str,
    user_id: CurrentUserId,
    session: DBSession,
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    rows = await webhook_service.deliveries(session, user_id, UUID(endpoint_id), limit)
    return success(
        [WebhookDeliveryResponse.model_validate(row).model_dump(mode="json") for row in rows]
    )
