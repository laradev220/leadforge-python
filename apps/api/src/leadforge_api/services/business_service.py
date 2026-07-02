"""Business service. Mirrors apps/api/src/services/business-service.ts."""

from __future__ import annotations

from uuid import UUID

from leadforge_database.models import (
    Business,
    Contact,
    LeadScore,
    SocialProfile,
    Website,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from leadforge_api.core.errors import not_found
from leadforge_api.core.queue import enqueue_website


async def list_businesses(
    session: AsyncSession,
    *,
    name: str | None,
    city: str | None,
    country: str | None,
    category: str | None,
    website_status: str | None,
    min_rating: float | None,
    max_rating: float | None,
    page: int,
    limit: int,
) -> tuple[list[Business], int]:
    where: list[ColumnElement[bool]] = []
    if name:
        where.append(Business.name.ilike(f"%{name}%"))
    if city:
        where.append(Business.city.ilike(f"%{city}%"))
    if country:
        where.append(Business.country == country)
    if category:
        where.append(Business.category.ilike(f"%{category}%"))
    if website_status:
        where.append(Business.website_status == website_status)
    if min_rating is not None or max_rating is not None:
        if min_rating is not None:
            where.append(Business.rating >= min_rating)
        if max_rating is not None:
            where.append(Business.rating <= max_rating)

    total = await session.scalar(select(func.count()).select_from(Business).where(*where))
    result = await session.execute(
        select(Business)
        .where(*where)
        .order_by(Business.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .options(
            selectinload(Business.lead_score),
            selectinload(Business.website),
        )
    )
    return list(result.scalars()), int(total or 0)


async def get_by_id(session: AsyncSession, business_id: UUID) -> Business:
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
        raise not_found("Business not found")
    return business


async def re_enrich(session: AsyncSession, business_id: UUID) -> None:
    result = await session.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if business is None:
        raise not_found("Business not found")
    await enqueue_website(business_id)


async def get_website(session: AsyncSession, business_id: UUID) -> Website | None:
    result = await session.execute(select(Website).where(Website.business_id == business_id))
    return result.scalar_one_or_none()


async def list_contacts(session: AsyncSession, business_id: UUID) -> list[Contact]:
    result = await session.execute(
        select(Contact)
        .where(Contact.business_id == business_id)
        .order_by(Contact.created_at.desc())
    )
    return list(result.scalars())


async def add_contact(
    session: AsyncSession, business_id: UUID, contact_type, value: str
) -> Contact:
    contact = Contact(
        business_id=business_id,
        type=contact_type,
        value=value,
        source="MANUAL",
    )
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    return contact


async def list_social_profiles(session: AsyncSession, business_id: UUID) -> list[SocialProfile]:
    result = await session.execute(
        select(SocialProfile)
        .where(SocialProfile.business_id == business_id)
        .order_by(SocialProfile.created_at.desc())
    )
    return list(result.scalars())


async def get_lead_score(session: AsyncSession, business_id: UUID) -> LeadScore | None:
    result = await session.execute(select(LeadScore).where(LeadScore.business_id == business_id))
    return result.scalar_one_or_none()
