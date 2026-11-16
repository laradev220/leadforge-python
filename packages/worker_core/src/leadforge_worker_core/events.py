"""Webhook event fan-out."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from leadforge_database import get_session_ctx
from leadforge_database.models import WebhookDelivery, WebhookEndpoint
from sqlalchemy import select

from leadforge_worker_core.core import enqueue_job


async def emit_event(user_id: UUID, event: str, data: dict[str, Any]) -> int:
    """Create delivery rows for matching endpoints and enqueue delivery jobs."""
    delivery_ids: list[str] = []
    async with get_session_ctx() as session:
        endpoints = list(
            (
                await session.execute(
                    select(WebhookEndpoint).where(
                        WebhookEndpoint.user_id == user_id,
                        WebhookEndpoint.active.is_(True),
                    )
                )
            ).scalars()
        )
        for endpoint in endpoints:
            if event not in (endpoint.events or []):
                continue
            delivery = WebhookDelivery(
                endpoint_id=endpoint.id,
                event=event,
                payload={"event": event, "data": data},
                status="PENDING",
            )
            session.add(delivery)
            await session.flush()
            delivery_ids.append(str(delivery.id))
        await session.commit()

    for delivery_id in delivery_ids:
        await enqueue_job("webhook", "deliver", {"delivery_id": delivery_id})
    return len(delivery_ids)
