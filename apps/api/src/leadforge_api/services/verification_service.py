"""Verification service: enqueue contact verification for a user's leads."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.queue import enqueue_verification
from leadforge_api.services import business_service, lead_service


async def enqueue_single(
    session: AsyncSession, user_id: UUID, business_id: UUID, *, force: bool = False
) -> None:
    """404 for leads outside the caller's workspace, then enqueue verification."""
    await business_service.get_by_id(session, user_id, business_id)
    await enqueue_verification(business_id, force=force)


async def enqueue_bulk(
    session: AsyncSession,
    user_id: UUID,
    *,
    filters,
    force: bool = False,
    limit: int = 500,
) -> int:
    """Queue verification for up to ``limit`` leads matching ``filters``."""
    ids = await lead_service.find_lead_ids(
        session,
        user_id,
        score_min=filters.score_min,
        score_max=filters.score_max,
        grade=filters.grade,
        website_status=filters.website_status,
        best_contact_method=filters.best_contact_method,
        city=filters.city,
        country=filters.country,
        verified_email=filters.verified_email,
        has_mobile=filters.has_mobile,
        limit=min(limit, filters.limit),
    )
    for business_id in ids:
        await enqueue_verification(business_id, force=force)
    return len(ids)
