"""Analytics service. Mirrors apps/api/src/routes/analytics.ts."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_database.models import Business, Contact, ContactType, LeadScore, SocialProfile


async def dashboard_stats(session: AsyncSession) -> dict:
    businesses, websites_found, emails_found, social_profiles_found, high_value_leads = await asyncio_gather_count(
        session
    )
    return {
        "businesses": businesses,
        "websitesFound": websites_found,
        "emailsFound": emails_found,
        "socialProfilesFound": social_profiles_found,
        "highValueLeads": high_value_leads,
    }


async def asyncio_gather_count(session: AsyncSession) -> tuple[int, int, int, int, int]:
    return await _counts(session)


async def _counts(session: AsyncSession) -> tuple[int, int, int, int, int]:
    businesses = await session.scalar(select(func.count()).select_from(Business)) or 0
    websites_found = await session.scalar(
        select(func.count()).select_from(Business).where(Business.website_status == "FOUND")
    ) or 0
    emails_found = await session.scalar(
        select(func.count()).select_from(Contact).where(Contact.type == ContactType.EMAIL)
    ) or 0
    social_profiles_found = await session.scalar(select(func.count()).select_from(SocialProfile)) or 0
    high_value_leads = await session.scalar(
        select(func.count()).select_from(LeadScore).where(LeadScore.score >= 80)
    ) or 0
    return int(businesses), int(websites_found), int(emails_found), int(social_profiles_found), int(high_value_leads)


async def lead_distribution(session: AsyncSession) -> dict[str, int]:
    grades = ["A+", "A", "B", "C", "D", "F"]
    distribution: dict[str, int] = {}
    for grade in grades:
        count = await session.scalar(
            select(func.count()).select_from(LeadScore).where(LeadScore.grade == grade)
        )
        distribution[grade] = int(count or 0)
    return distribution
