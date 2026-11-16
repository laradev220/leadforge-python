"""Lead service. Mirrors apps/api/src/services/lead-service.ts."""

from __future__ import annotations

from uuid import UUID

from leadforge_database.models import (
    Business,
    Contact,
    ContactType,
    LeadScore,
    PhoneLineType,
    VerificationStatus,
)
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload
from sqlalchemy.sql.elements import ColumnElement

from leadforge_api.core.errors import not_found
from leadforge_api.core.tenancy import user_business_ids


def lead_where(
    user_id: UUID,
    *,
    score_min: int | None,
    score_max: int | None,
    grade: str | None,
    website_status: str | None,
    best_contact_method: str | None,
    city: str | None,
    country: str | None,
    verified_email: bool = False,
    has_mobile: bool = False,
) -> list[ColumnElement[bool]]:
    """Shared filter builder for lead list, counts and bulk verification."""
    where: list[ColumnElement[bool]] = [Business.id.in_(user_business_ids(user_id))]
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
    if verified_email:
        where.append(
            exists().where(
                Contact.business_id == Business.id,
                Contact.type == ContactType.EMAIL,
                Contact.verification_status == VerificationStatus.VALID,
            )
        )
    if has_mobile:
        where.append(
            exists().where(
                Contact.business_id == Business.id,
                Contact.type == ContactType.PHONE,
                Contact.line_type == PhoneLineType.MOBILE,
            )
        )
    return where


async def list_leads(
    session: AsyncSession,
    user_id: UUID,
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
    verified_email: bool = False,
    has_mobile: bool = False,
) -> tuple[list[Business], int]:
    # Explicit INNER JOIN to LeadScore keeps lead filters correlated; the
    # tenant subquery keeps results scoped to this user's discovered leads.
    query = select(Business).join(LeadScore, Business.id == LeadScore.business_id)
    count_query = (
        select(func.count())
        .select_from(Business)
        .join(LeadScore, Business.id == LeadScore.business_id)
    )

    where = lead_where(
        user_id,
        score_min=score_min,
        score_max=score_max,
        grade=grade,
        website_status=website_status,
        best_contact_method=best_contact_method,
        city=city,
        country=country,
        verified_email=verified_email,
        has_mobile=has_mobile,
    )

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


async def find_lead_ids(
    session: AsyncSession,
    user_id: UUID,
    *,
    score_min: int | None = None,
    score_max: int | None = None,
    grade: str | None = None,
    website_status: str | None = None,
    best_contact_method: str | None = None,
    city: str | None = None,
    country: str | None = None,
    verified_email: bool = False,
    has_mobile: bool = False,
    limit: int = 500,
) -> list[UUID]:
    """IDs matching the same filters as the lead list, capped for bulk actions."""
    where = lead_where(
        user_id,
        score_min=score_min,
        score_max=score_max,
        grade=grade,
        website_status=website_status,
        best_contact_method=best_contact_method,
        city=city,
        country=country,
        verified_email=verified_email,
        has_mobile=has_mobile,
    )
    result = await session.execute(
        select(Business.id)
        .join(LeadScore, Business.id == LeadScore.business_id)
        .where(*where)
        .order_by(Business.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def lead_stats(
    session: AsyncSession,
    user_id: UUID,
    *,
    score_min: int | None = None,
    score_max: int | None = None,
    grade: str | None = None,
    website_status: str | None = None,
    best_contact_method: str | None = None,
    city: str | None = None,
    country: str | None = None,
) -> dict[str, int]:
    """Counts for the list summary chips, ignoring the verified/mobile toggles."""

    async def _count(
        *, verified_email: bool = False, has_mobile: bool = False, checked_email: bool = False
    ) -> int:
        where = lead_where(
            user_id,
            score_min=score_min,
            score_max=score_max,
            grade=grade,
            website_status=website_status,
            best_contact_method=best_contact_method,
            city=city,
            country=country,
            verified_email=verified_email,
            has_mobile=has_mobile,
        )
        if checked_email:
            where.append(
                exists().where(
                    Contact.business_id == Business.id,
                    Contact.type == ContactType.EMAIL,
                    Contact.verification_status.in_(
                        [VerificationStatus.VALID, VerificationStatus.RISKY]
                    ),
                )
            )
        value = await session.scalar(
            select(func.count())
            .select_from(Business)
            .join(LeadScore, Business.id == LeadScore.business_id)
            .where(*where)
        )
        return int(value or 0)

    return {
        "total_count": await _count(),
        "verified_email_count": await _count(verified_email=True),
        "checked_email_count": await _count(checked_email=True),
        "mobile_count": await _count(has_mobile=True),
    }


async def get_lead(session: AsyncSession, user_id: UUID, business_id: UUID) -> Business:
    result = await session.execute(
        select(Business)
        .where(
            Business.id == business_id,
            Business.id.in_(user_business_ids(user_id)),
        )
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
