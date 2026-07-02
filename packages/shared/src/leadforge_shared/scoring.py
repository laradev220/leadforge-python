"""Pure lead scoring engine. 1:1 port of packages/scoring-engine/src/index.ts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from leadforge_shared.constants import CONTACT_PRIORITY

WebsiteStatusInput = Literal["UNKNOWN", "FOUND", "NOT_FOUND", "INVALID"]


@dataclass(frozen=True)
class WebsiteInput:
    ssl_enabled: bool | None
    is_reachable: bool | None
    mobile_friendly: bool | None
    seo_score: int | None
    has_contact_form: bool | None = None


@dataclass(frozen=True)
class ContactInput:
    type: str


@dataclass(frozen=True)
class SocialProfileInput:
    platform: str
    last_activity_at: datetime | str | None = None
    followers: int | None = None


@dataclass(frozen=True)
class ScoringInput:
    website_status: WebsiteStatusInput
    website: WebsiteInput | None
    contacts: list[ContactInput]
    social_profiles: list[SocialProfileInput]
    rating: float | None
    review_count: int | None
    has_phone: bool
    has_address: bool


@dataclass(frozen=True)
class ScoringOutput:
    score: int
    grade: str
    website_opportunity_score: int
    contact_quality_score: int
    social_activity_score: int
    business_validation_score: int
    review_score: int
    best_contact_method: str | None


def calculate_lead_score(scoring_input: ScoringInput) -> ScoringOutput:
    website_opp = _calc_website_opportunity(scoring_input)
    contact_quality = _calc_contact_availability(scoring_input)
    social_activity = _calc_social_activity(scoring_input)
    business_validation = _calc_business_validation(scoring_input)
    review = _calc_review_signal(scoring_input)

    total = min(
        website_opp + contact_quality + social_activity + business_validation + review,
        100,
    )

    return ScoringOutput(
        score=total,
        grade=_get_grade(total),
        website_opportunity_score=website_opp,
        contact_quality_score=contact_quality,
        social_activity_score=social_activity,
        business_validation_score=business_validation,
        review_score=review,
        best_contact_method=_determine_best_contact_method(scoring_input),
    )


def _calc_website_opportunity(scoring_input: ScoringInput) -> int:
    if scoring_input.website_status == "NOT_FOUND":
        return 40
    if scoring_input.website_status == "INVALID":
        return 40

    website = scoring_input.website
    if website is None or not website.is_reachable:
        return 40

    if not website.ssl_enabled or not website.has_contact_form:
        return 25

    if not website.mobile_friendly or (website.seo_score is not None and website.seo_score < 50):
        return 15

    return 0


_CONTACT_POINTS = {
    "EMAIL": 10,
    "CONTACT_FORM": 8,
    "WHATSAPP": 8,
    "LINKEDIN": 5,
    "FACEBOOK": 4,
    "INSTAGRAM": 4,
    "PHONE": 2,
}


def _calc_contact_availability(scoring_input: ScoringInput) -> int:
    points = 0
    for contact in scoring_input.contacts:
        points += _CONTACT_POINTS.get(contact.type, 0)
    return min(points, 20)


def _calc_social_activity(scoring_input: ScoringInput) -> int:
    if not scoring_input.social_profiles:
        return 0

    max_points = 0
    now = datetime.now(UTC)

    for profile in scoring_input.social_profiles:
        if profile.last_activity_at is None:
            max_points = max(max_points, 5)
            continue

        last_active = profile.last_activity_at
        if isinstance(last_active, str):
            last_active = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=UTC)

        days_since = (now - last_active).total_seconds() / 86400

        if days_since <= 30:
            max_points = max(max_points, 20)
        elif days_since <= 90:
            max_points = max(max_points, 12)
        elif days_since <= 180:
            max_points = max(max_points, 5)
        else:
            max_points = max(max_points, 0)

    return max_points


def _calc_business_validation(scoring_input: ScoringInput) -> int:
    points = 0
    if scoring_input.has_phone:
        points += 2
    if scoring_input.website_status == "FOUND" and (
        scoring_input.website is not None and scoring_input.website.is_reachable
    ):
        points += 2
    if scoring_input.social_profiles:
        points += 2
    if scoring_input.has_address:
        points += 2
    if scoring_input.review_count is not None and scoring_input.review_count > 0:
        points += 2
    return min(points, 10)


def _calc_review_signal(scoring_input: ScoringInput) -> int:
    count = scoring_input.review_count or 0
    if count >= 200:
        return 10
    if count >= 51:
        return 8
    if count >= 11:
        return 5
    if count >= 1:
        return 2
    return 0


def _get_grade(score: int) -> str:
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _determine_best_contact_method(scoring_input: ScoringInput) -> str | None:
    contact_types = {c.type for c in scoring_input.contacts}
    social_types = {p.platform for p in scoring_input.social_profiles}

    sorted_priority = sorted(CONTACT_PRIORITY.items(), key=lambda item: item[1])
    for type_, _ in sorted_priority:
        if type_ in contact_types:
            return type_

    for type_, _ in sorted_priority:
        if type_ in social_types:
            return type_

    return None
