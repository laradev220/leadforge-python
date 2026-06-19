"""Social profile routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from leadforge_api.core.deps import DBSession
from leadforge_api.core.errors import not_found
from leadforge_api.core.response import success
from leadforge_api.schemas import SocialProfileResponse
from leadforge_database.models import SocialProfile

router = APIRouter(prefix="/social-profiles", tags=["social-profiles"])


@router.get("/{profile_id}", response_model=None)
async def get_social_profile(profile_id: str, session: DBSession) -> dict:
    result = await session.execute(
        select(SocialProfile).where(SocialProfile.id == UUID(profile_id))
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise not_found("Social profile not found")
    return success(SocialProfileResponse.model_validate(profile).model_dump(mode="json"))
