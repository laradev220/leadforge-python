"""Analytics service. Mirrors apps/api/src/routes/analytics.ts."""

from __future__ import annotations

from uuid import UUID

from leadforge_database.models import (
    Business,
    Contact,
    ContactType,
    LeadScore,
    SocialProfile,
    WebsiteStatus,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.tenancy import user_business_ids


async def dashboard_stats(session: AsyncSession, user_id: UUID) -> dict:
    scope = Business.id.in_(user_business_ids(user_id))

    businesses = await session.scalar(select(func.count()).select_from(Business).where(scope)) or 0
    websites_found = (
        await session.scalar(
            select(func.count())
            .select_from(Business)
            .where(scope, Business.website_status == WebsiteStatus.FOUND)
        )
        or 0
    )
    emails_found = (
        await session.scalar(
            select(func.count())
            .select_from(Contact)
            .join(Business, Contact.business_id == Business.id)
            .where(scope, Contact.type == ContactType.EMAIL)
        )
        or 0
    )
    social_profiles_found = (
        await session.scalar(
            select(func.count())
            .select_from(SocialProfile)
            .join(Business, SocialProfile.business_id == Business.id)
            .where(scope)
        )
        or 0
    )
    high_value_leads = (
        await session.scalar(
            select(func.count())
            .select_from(LeadScore)
            .join(Business, LeadScore.business_id == Business.id)
            .where(scope, LeadScore.score >= 80)
        )
        or 0
    )
    return {
        "businesses": int(businesses),
        "websitesFound": int(websites_found),
        "emailsFound": int(emails_found),
        "socialProfilesFound": int(social_profiles_found),
        "highValueLeads": int(high_value_leads),
    }


async def lead_distribution(session: AsyncSession, user_id: UUID) -> dict[str, int]:
    scope = Business.id.in_(user_business_ids(user_id))
    grades = ["A+", "A", "B", "C", "D", "F"]
    distribution: dict[str, int] = {}
    for grade in grades:
        count = await session.scalar(
            select(func.count())
            .select_from(LeadScore)
            .join(Business, LeadScore.business_id == Business.id)
            .where(scope, LeadScore.grade == grade)
        )
        distribution[grade] = int(count or 0)
    return distribution
