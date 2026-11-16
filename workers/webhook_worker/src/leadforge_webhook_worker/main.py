"""Deliver webhook events with HMAC signing, SSRF checks and retries."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog
from leadforge_database import get_session_ctx
from leadforge_database.models import WebhookDelivery, WebhookEndpoint
from leadforge_shared.net import validate_public_https_url
from leadforge_worker_core.core import WorkerWrapper, run_worker
from sqlalchemy import select

logger = structlog.get_logger("worker.webhook")
MAX_ATTEMPTS = 5


def sign(secret: str, timestamp: int, body: bytes) -> str:
    message = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


async def webhook_processor(data: dict, log) -> None:
    delivery_id = UUID(str(data["delivery_id"]))

    async with get_session_ctx() as session:
        row = (
            await session.execute(
                select(WebhookDelivery, WebhookEndpoint)
                .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
                .where(WebhookDelivery.id == delivery_id)
            )
        ).first()
        if row is None:
            log.warning("webhook_delivery_missing", deliveryId=str(delivery_id))
            return
        delivery, endpoint = row

        if not endpoint.active:
            delivery.status = "FAILED"
            delivery.error = "endpoint_inactive"
            delivery.completed_at = datetime.now(UTC)
            await session.commit()
            return

        delivery.attempts += 1
        timestamp = int(time.time())
        body = json.dumps(
            {
                "event": delivery.event,
                "data": delivery.payload.get("data", {}),
                "delivery_id": str(delivery.id),
                "timestamp": timestamp,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        headers = {
            "Content-Type": "application/json",
            "X-LeadForge-Event": delivery.event,
            "X-LeadForge-Delivery": str(delivery.id),
            "X-LeadForge-Timestamp": str(timestamp),
            "X-LeadForge-Signature": sign(endpoint.secret, timestamp, body),
        }

        response_code = None
        error = None
        try:
            await validate_public_https_url(endpoint.url)
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                response = await client.post(endpoint.url, content=body, headers=headers)
            response_code = response.status_code
            if not 200 <= response.status_code < 300:
                error = f"http_{response.status_code}"
        except Exception as exc:
            error = str(exc)[:500]

        now = datetime.now(UTC)
        endpoint.last_delivery_at = now
        delivery.response_code = response_code
        delivery.error = error

        if error is None:
            delivery.status = "SUCCESS"
            delivery.completed_at = now
            endpoint.failure_count = 0
        else:
            endpoint.failure_count += 1
            if endpoint.failure_count >= 20:
                endpoint.active = False
            if delivery.attempts >= MAX_ATTEMPTS:
                delivery.status = "FAILED"
                delivery.completed_at = now
            else:
                delivery.status = "RETRYING"

        await session.commit()
        should_retry = delivery.status == "RETRYING"
        attempts = delivery.attempts

    if should_retry:
        log.warning(
            "webhook_retry",
            deliveryId=str(delivery_id),
            attempts=attempts,
            error=error,
        )
        raise RuntimeError(f"webhook delivery failed: {error}")

    log.info(
        "webhook_delivered" if error is None else "webhook_failed",
        deliveryId=str(delivery_id),
        attempts=attempts,
        response=response_code,
    )


worker: WorkerWrapper[dict] = WorkerWrapper("webhook", webhook_processor)


async def deliver(ctx: dict, delivery_id: str) -> None:
    await worker(ctx, {"delivery_id": delivery_id})


def main() -> None:
    run_worker("webhook", deliver)


if __name__ == "__main__":
    main()
