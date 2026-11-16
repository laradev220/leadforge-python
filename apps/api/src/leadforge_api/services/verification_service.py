"""Verification service: enqueue contact verification for a user's leads."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.queue import enqueue_verification
from leadforge_api.services import business_service


async def enqueue_single(
    session: AsyncSession, user_id: UUID, business_id: UUID, *, force: bool = False
) -> None:
    """404 for leads outside the caller's workspace, then enqueue verification."""
    await business_service.get_by_id(session, user_id, business_id)
    await enqueue_verification(business_id, force=force)
