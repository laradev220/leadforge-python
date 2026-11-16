"""Webhook endpoint management."""

from __future__ import annotations

import secrets
from uuid import UUID

from leadforge_database.models import WebhookDelivery, WebhookEndpoint
from leadforge_shared.net import validate_public_https_url
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.errors import bad_request, not_found


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[WebhookEndpoint]:
    result = await session.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.user_id == user_id)
        .order_by(WebhookEndpoint.created_at.desc())
    )
    return list(result.scalars())


async def _get(session: AsyncSession, user_id: UUID, endpoint_id: UUID) -> WebhookEndpoint:
    endpoint = (
        await session.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.id == endpoint_id, WebhookEndpoint.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if endpoint is None:
        raise not_found("Webhook endpoint not found")
    return endpoint


async def create(
    session: AsyncSession, user_id: UUID, url: str, events: list[str]
) -> WebhookEndpoint:
    try:
        url = await validate_public_https_url(url)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    endpoint = WebhookEndpoint(
        user_id=user_id,
        url=url,
        events=events,
        secret=secrets.token_hex(32),
    )
    session.add(endpoint)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint


async def update(session: AsyncSession, user_id: UUID, endpoint_id: UUID, data) -> WebhookEndpoint:
    endpoint = await _get(session, user_id, endpoint_id)
    if data.url is not None and data.url != endpoint.url:
        try:
            endpoint.url = await validate_public_https_url(data.url)
        except ValueError as exc:
            raise bad_request(str(exc)) from exc
    if data.events is not None:
        endpoint.events = data.events
    if data.active is not None:
        endpoint.active = data.active
        if data.active:
            endpoint.failure_count = 0
    await session.commit()
    await session.refresh(endpoint)
    return endpoint


async def rotate_secret(session: AsyncSession, user_id: UUID, endpoint_id: UUID) -> WebhookEndpoint:
    endpoint = await _get(session, user_id, endpoint_id)
    endpoint.secret = secrets.token_hex(32)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint


async def delete(session: AsyncSession, user_id: UUID, endpoint_id: UUID) -> None:
    endpoint = await _get(session, user_id, endpoint_id)
    await session.delete(endpoint)
    await session.commit()


async def deliveries(
    session: AsyncSession, user_id: UUID, endpoint_id: UUID, limit: int = 20
) -> list[WebhookDelivery]:
    await _get(session, user_id, endpoint_id)
    result = await session.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == endpoint_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())
