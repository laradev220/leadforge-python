"""Business routes (+ sub-routes: website, contacts, social-profiles)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.pagination import get_pagination
from leadforge_api.core.response import paginated, success
from leadforge_api.schemas import (
    AddContactRequest,
    BusinessResponse,
    ContactResponse,
    SocialProfileResponse,
    WebsiteResponse,
)
from leadforge_api.services import business_service, verification_service

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("", response_model=None)
async def list_businesses(
    user_id: CurrentUserId,
    session: DBSession,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    name: str | None = None,
    city: str | None = None,
    country: str | None = None,
    category: str | None = None,
    website_status: str | None = None,
    min_rating: float | None = None,
    max_rating: float | None = None,
) -> dict:
    pagination = get_pagination({"page": str(page), "limit": str(limit)})
    businesses, total = await business_service.list_businesses(
        session,
        user_id,
        name=name,
        city=city,
        country=country,
        category=category,
        website_status=website_status,
        min_rating=min_rating,
        max_rating=max_rating,
        page=pagination.page,
        limit=pagination.limit,
    )
    return paginated(
        [BusinessResponse.model_validate(b).model_dump(mode="json") for b in businesses],
        total,
        pagination.page,
        pagination.limit,
    )


@router.get("/{business_id}", response_model=None)
async def get_business(business_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    business = await business_service.get_by_id(session, user_id, UUID(business_id))
    return success(BusinessResponse.model_validate(business).model_dump(mode="json"))


@router.post("/{business_id}/re-enrich", response_model=None)
async def re_enrich(business_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    await business_service.re_enrich(session, user_id, UUID(business_id))
    return success({"reEnriched": True})


@router.post("/{business_id}/verify", response_model=None, status_code=202)
async def verify_business(
    business_id: str,
    user_id: CurrentUserId,
    session: DBSession,
    force: bool = Query(False),
) -> dict:
    await verification_service.enqueue_single(session, user_id, UUID(business_id), force=force)
    return success({"queued": True})


@router.get("/{business_id}/website", response_model=None)
async def get_business_website(
    business_id: str, user_id: CurrentUserId, session: DBSession
) -> dict:
    await business_service.get_by_id(session, user_id, UUID(business_id))
    website = await business_service.get_website(session, UUID(business_id))
    if website is None:
        return success(None)
    return success(WebsiteResponse.model_validate(website).model_dump(mode="json"))


@router.get("/{business_id}/contacts", response_model=None)
async def list_business_contacts(
    business_id: str, user_id: CurrentUserId, session: DBSession
) -> dict:
    contacts = await business_service.list_contacts(session, user_id, UUID(business_id))
    return success([ContactResponse.model_validate(c).model_dump(mode="json") for c in contacts])


@router.post("/{business_id}/contacts", response_model=None, status_code=201)
async def add_business_contact(
    business_id: str, body: AddContactRequest, user_id: CurrentUserId, session: DBSession
) -> dict:
    contact = await business_service.add_contact(
        session, user_id, UUID(business_id), body.type, body.value
    )
    return success(ContactResponse.model_validate(contact).model_dump(mode="json"))


@router.get("/{business_id}/social-profiles", response_model=None)
async def list_business_social_profiles(
    business_id: str, user_id: CurrentUserId, session: DBSession
) -> dict:
    profiles = await business_service.list_social_profiles(session, user_id, UUID(business_id))
    return success(
        [SocialProfileResponse.model_validate(p).model_dump(mode="json") for p in profiles]
    )
