"""Lead routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from leadforge_database.provenance import provenance_for_business

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.pagination import get_pagination
from leadforge_api.core.response import paginated, success
from leadforge_api.schemas import LeadResponse
from leadforge_api.services import lead_service

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=None)
async def list_leads(
    user_id: CurrentUserId,
    session: DBSession,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    score_min: int | None = None,
    score_max: int | None = None,
    grade: str | None = None,
    website_status: str | None = None,
    best_contact_method: str | None = None,
    city: str | None = None,
    country: str | None = None,
    verified_email: bool = False,
    has_mobile: bool = False,
    include_stats: bool = False,
) -> dict:
    pagination = get_pagination({"page": str(page), "limit": str(limit)})
    businesses, total = await lead_service.list_leads(
        session,
        user_id,
        score_min=score_min,
        score_max=score_max,
        grade=grade,
        website_status=website_status,
        best_contact_method=best_contact_method,
        city=city,
        country=country,
        page=pagination.page,
        limit=pagination.limit,
        verified_email=verified_email,
        has_mobile=has_mobile,
    )
    extra_meta = None
    if include_stats:
        extra_meta = await lead_service.lead_stats(
            session,
            user_id,
            score_min=score_min,
            score_max=score_max,
            grade=grade,
            website_status=website_status,
            best_contact_method=best_contact_method,
            city=city,
            country=country,
        )
    return paginated(
        [
            LeadResponse.model_validate(
                {
                    "business": b,
                    "lead_score": b.lead_score,
                    "contacts": b.contacts or [],
                    "social_profiles": b.social_profiles or [],
                    "website": b.website,
                }
            ).model_dump(mode="json")
            for b in businesses
        ],
        total,
        pagination.page,
        pagination.limit,
        extra_meta,
    )


@router.get("/{business_id}", response_model=None)
async def get_lead(business_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    business = await lead_service.get_lead(session, user_id, UUID(business_id))
    provenance = await provenance_for_business(session, business.id)
    return success(
        LeadResponse.model_validate(
            {
                "business": business,
                "lead_score": business.lead_score,
                "contacts": business.contacts or [],
                "social_profiles": business.social_profiles or [],
                "website": business.website,
                "provenance": provenance,
            }
        ).model_dump(mode="json")
    )
