"""Social profile routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from leadforge_database.models import Business, SocialProfile
from sqlalchemy import func, select
from sqlalchemy.sql.elements import ColumnElement

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.errors import not_found
from leadforge_api.core.pagination import get_pagination
from leadforge_api.core.response import paginated, success
from leadforge_api.core.tenancy import user_business_ids
from leadforge_api.schemas import SocialProfileResponse, SocialProfileWithBusinessResponse

router = APIRouter(prefix="/social-profiles", tags=["social-profiles"])


@router.get("", response_model=None)
async def list_social_profiles(
    user_id: CurrentUserId,
    session: DBSession,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    platform: str | None = None,
    q: str | None = None,
    min_followers: int | None = None,
    sort_by: str = Query("followers", pattern="^(followers|posts_count|created_at)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict:
    pagination = get_pagination({"page": str(page), "limit": str(limit)})

    where: list[ColumnElement[bool]] = [SocialProfile.business_id.in_(user_business_ids(user_id))]
    if platform:
        where.append(SocialProfile.platform == platform.upper())
    if q:
        where.append(
            SocialProfile.username.ilike(f"%{q}%")
            | SocialProfile.bio.ilike(f"%{q}%")
            | Business.name.ilike(f"%{q}%")
        )
    if min_followers is not None:
        where.append(SocialProfile.followers >= min_followers)

    sort_col = getattr(SocialProfile, sort_by)
    order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()

    count_q = (
        select(func.count())
        .select_from(SocialProfile)
        .join(Business, SocialProfile.business_id == Business.id)
        .where(*where)
    )
    total = await session.scalar(count_q)

    q_stmt = (
        select(SocialProfile, Business.name, Business.city)
        .join(Business, SocialProfile.business_id == Business.id)
        .where(*where)
        .order_by(order)
        .offset(pagination.skip)
        .limit(pagination.limit)
    )

    result = await session.execute(q_stmt)
    rows = result.all()

    data = []
    for sp, biz_name, biz_city in rows:
        entry = SocialProfileWithBusinessResponse.model_validate(sp).model_dump(mode="json")
        entry["business_name"] = biz_name
        entry["business_city"] = biz_city
        data.append(entry)

    return paginated(data, int(total or 0), pagination.page, pagination.limit)


@router.get("/{profile_id}", response_model=None)
async def get_social_profile(profile_id: str, user_id: CurrentUserId, session: DBSession) -> dict:
    result = await session.execute(
        select(SocialProfile).where(
            SocialProfile.id == UUID(profile_id),
            SocialProfile.business_id.in_(user_business_ids(user_id)),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise not_found("Social profile not found")
    return success(SocialProfileResponse.model_validate(profile).model_dump(mode="json"))
