"""Lead service. Mirrors apps/api/src/services/lead-service.ts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from leadforge_database.models import Business, LeadScore
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from leadforge_api.core.errors import not_found


async def list_leads(
    session: AsyncSession,
    *,
    score_min: int | None,
    score_max: int | None,
    grade: str | None,
    website_status: str | None,
    best_contact_method: str | None,
    city: str | None,
    country: str | None,
    page: int,
    limit: int,
) -> tuple[list[Business], int]:
    # Build base query with explicit INNER JOIN to LeadScore
    # This ensures lead_score filters are properly correlated with the business
    query = select(Business).join(LeadScore, Business.id == LeadScore.business_id)
    count_query = (
        select(func.count())
        .select_from(Business)
        .join(LeadScore, Business.id == LeadScore.business_id)
    )

    where = []
    if score_min is not None:
        where.append(LeadScore.score >= score_min)
    if score_max is not None:
        where.append(LeadScore.score <= score_max)
    if grade:
        where.append(LeadScore.grade == grade)
    if best_contact_method:
        where.append(LeadScore.best_contact_method == best_contact_method)
    if website_status:
        where.append(Business.website_status == website_status)
    if city:
        where.append(Business.city.ilike(f"%{city}%"))
    if country:
        where.append(Business.country == country)

    total = await session.scalar(count_query.where(*where))
    result = await session.execute(
        query.where(*where)
        .order_by(Business.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .options(
            contains_eager(Business.lead_score),
            selectinload(Business.website),
            selectinload(Business.contacts),
            selectinload(Business.social_profiles),
        )
    )
    return list(result.scalars()), int(total or 0)


async def get_lead(session: AsyncSession, business_id: UUID) -> Business:
    result = await session.execute(
        select(Business)
        .where(Business.id == business_id)
        .options(
            selectinload(Business.website),
            selectinload(Business.contacts),
            selectinload(Business.social_profiles),
            selectinload(Business.lead_score),
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise not_found("Lead not found")
    return business


def _coerce_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    if not filters:
        return {}
    return {k: v for k, v in filters.items() if v is not None}
