"""Verification capability discovery for the UI."""

from __future__ import annotations

from fastapi import APIRouter
from leadforge_config import get_settings

from leadforge_api.core.deps import CurrentUserId
from leadforge_api.core.response import success

router = APIRouter(prefix="/verification", tags=["verification"])


@router.get("/capabilities", response_model=None)
async def capabilities(user_id: CurrentUserId) -> dict:
    settings = get_settings()
    provider = (settings.email_verifier_provider or "mx").strip().lower()
    supports_valid = provider == "smtp" or (
        provider == "zerobounce" and bool(settings.zero_bounce_api_key)
    )
    return success(
        {
            "provider": provider,
            "supports_valid": supports_valid,
            "supports_domain_checked": True,
            "max_age_days": settings.verify_max_age_days,
        }
    )
