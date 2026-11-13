"""Scoring worker. Mirrors workers/scoring-worker/src/index.ts."""

from uuid import UUID

from leadforge_database import get_session_ctx
from leadforge_database.models import (
    Business,
    Contact,
    LeadScore,
    SearchJob,
    SearchJobBusiness,
    SocialProfile,
    Website,
)
from leadforge_shared.scoring import (
    ContactInput,
    ScoringInput,
    SocialProfileInput,
    WebsiteInput,
    calculate_lead_score,
)
from leadforge_shared.types import ScoringJobData
from leadforge_worker_core.core import WorkerWrapper
from sqlalchemy import func, select, update


async def scoring_processor(data: ScoringJobData, logger):
    business_id = data.business_id
    logger.info("calculating_score", businessId=str(business_id))

    async with get_session_ctx() as session:
        # Fetch all data for scoring
        res_biz = await session.execute(select(Business).where(Business.id == business_id))
        business = res_biz.scalar_one_or_none()
        if not business:
            logger.error("business_not_found", businessId=str(business_id))
            raise ValueError("Business not found")

        res_web = await session.execute(select(Website).where(Website.business_id == business_id))
        website = res_web.scalar_one_or_none()

        res_con = await session.execute(select(Contact).where(Contact.business_id == business_id))
        contacts = res_con.scalars().all()

        res_soc = await session.execute(
            select(SocialProfile).where(SocialProfile.business_id == business_id)
        )
        socials = res_soc.scalars().all()

        # Build scoring input
        input_data = ScoringInput(
            website_status=business.website_status.value,
            website=WebsiteInput(
                ssl_enabled=website.ssl_enabled if website else None,
                is_reachable=website.is_reachable if website else None,
                mobile_friendly=website.mobile_friendly if website else None,
                seo_score=website.seo_score if website else None,
                has_contact_form=any(c.type == "CONTACT_FORM" for c in contacts),
            )
            if website
            else None,
            contacts=[ContactInput(type=c.type.value) for c in contacts],
            social_profiles=[
                SocialProfileInput(
                    platform=p.platform.value,
                    last_activity_at=p.last_activity_at,
                    followers=p.followers,
                )
                for p in socials
            ],
            rating=business.rating,
            review_count=business.review_count,
            has_phone=bool(business.phone),
            has_address=bool(business.address),
        )

        result = calculate_lead_score(input_data)

        # Upsert lead score
        res_score = await session.execute(
            select(LeadScore).where(LeadScore.business_id == business_id)
        )
        score_rec = res_score.scalar_one_or_none()

        if score_rec:
            score_rec.score = result.score
            score_rec.grade = result.grade
            score_rec.best_contact_method = result.best_contact_method
            score_rec.website_opportunity_score = result.website_opportunity_score
            score_rec.social_activity_score = result.social_activity_score
            score_rec.contact_quality_score = result.contact_quality_score
            score_rec.review_score = result.review_score
            score_rec.business_validation_score = result.business_validation_score
        else:
            session.add(
                LeadScore(
                    business_id=business_id,
                    score=result.score,
                    grade=result.grade,
                    best_contact_method=result.best_contact_method,
                    website_opportunity_score=result.website_opportunity_score,
                    social_activity_score=result.social_activity_score,
                    contact_quality_score=result.contact_quality_score,
                    review_score=result.review_score,
                    business_validation_score=result.business_validation_score,
                )
            )

        await _refresh_search_job_progress(session, business_id)
        await session.commit()
        logger.info(
            "scoring_completed", businessId=str(business_id), score=result.score, grade=result.grade
        )


async def _refresh_search_job_progress(session, business_id) -> None:
    """Recompute ``total_enriched`` for jobs linked to this business.

    Idempotent: re-scoring a lead does not inflate the counter.
    """
    enriched_count = (
        select(func.count())
        .select_from(SearchJobBusiness)
        .join(LeadScore, LeadScore.business_id == SearchJobBusiness.business_id)
        .where(SearchJobBusiness.search_job_id == SearchJob.id)
        .scalar_subquery()
    )
    linked_jobs = select(SearchJobBusiness.search_job_id).where(
        SearchJobBusiness.business_id == business_id
    )
    await session.execute(
        update(SearchJob).where(SearchJob.id.in_(linked_jobs)).values(total_enriched=enriched_count)
    )


worker: WorkerWrapper[ScoringJobData] = WorkerWrapper("scoring", scoring_processor)


# ── Module-level arq function ──────────────────────────────────────────────


async def scoring(ctx: dict, business_id: str) -> None:
    """Arq entry point."""
    data = ScoringJobData(business_id=UUID(business_id))
    await worker(ctx, data)


def main():
    """Entrypoint — arq 0.28's Worker.run() is synchronous."""
    from leadforge_worker_core.core import run_worker

    run_worker("scoring", scoring)


if __name__ == "__main__":
    main()
