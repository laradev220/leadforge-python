"""Unit tests for the scoring engine. Ported from tests/unit/scoring.test.ts."""

import pytest
from leadforge_shared.scoring import calculate_lead_score, ScoringInput

def make_base_input() -> ScoringInput:
    """Plain helper — not a pytest fixture (called directly by tests)."""
    return ScoringInput(
        website_status="NOT_FOUND",
        website=None,
        contacts=[],
        social_profiles=[],
        rating=None,
        review_count=None,
        has_phone=False,
        has_address=True,
    )

def test_no_website_opportunity():
    base = make_base_input()
    result = calculate_lead_score(base)
    assert result.website_opportunity_score == 40
    assert result.score >= 40

def test_modern_website_opportunity():
    from leadforge_shared.scoring import WebsiteInput
    base = make_base_input()
    result = calculate_lead_score(ScoringInput(
        website_status="FOUND",
        website=WebsiteInput(
            ssl_enabled=True,
            is_reachable=True,
            mobile_friendly=True,
            seo_score=80,
            has_contact_form=True,
        ),
        contacts=[],
        social_profiles=[],
        rating=None,
        review_count=None,
        has_phone=False,
        has_address=True,
    ))
    assert result.website_opportunity_score == 0

def test_weak_website_opportunity():
    from leadforge_shared.scoring import WebsiteInput
    base = make_base_input()
    result = calculate_lead_score(ScoringInput(
        website_status="FOUND",
        website=WebsiteInput(
            ssl_enabled=False,
            is_reachable=True,
            mobile_friendly=None,
            seo_score=None,
            has_contact_form=False,
        ),
        contacts=[],
        social_profiles=[],
        rating=None,
        review_count=None,
        has_phone=False,
        has_address=True,
    ))
    assert result.website_opportunity_score == 25

def test_email_contact_score():
    from leadforge_shared.scoring import ContactInput
    base = make_base_input()
    result = calculate_lead_score(ScoringInput(
        website_status=base.website_status,
        website=base.website,
        contacts=[ContactInput(type="EMAIL")],
        social_profiles=[],
        rating=None,
        review_count=None,
        has_phone=False,
        has_address=True,
    ))
    assert result.contact_quality_score == 10

def test_contact_score_cap():
    from leadforge_shared.scoring import ContactInput
    base = make_base_input()
    result = calculate_lead_score(ScoringInput(
        website_status=base.website_status,
        website=base.website,
        contacts=[
            ContactInput(type="EMAIL"),
            ContactInput(type="WHATSAPP"),
            ContactInput(type="LINKEDIN"),
        ],
        social_profiles=[],
        rating=None,
        review_count=None,
        has_phone=False,
        has_address=True,
    ))
    assert result.contact_quality_score == 20

def test_recent_social_activity():
    from leadforge_shared.scoring import SocialProfileInput
    from datetime import datetime, timezone
    base = make_base_input()
    result = calculate_lead_score(ScoringInput(
        website_status=base.website_status,
        website=base.website,
        contacts=[],
        social_profiles=[SocialProfileInput(platform="FACEBOOK", last_activity_at=datetime.now(timezone.utc))],
        rating=None,
        review_count=None,
        has_phone=False,
        has_address=True,
    ))
    assert result.social_activity_score == 20

def test_no_social_activity():
    base = make_base_input()
    result = calculate_lead_score(ScoringInput(
        website_status=base.website_status,
        website=base.website,
        contacts=[],
        social_profiles=[],
        rating=None,
        review_count=None,
        has_phone=False,
        has_address=True,
    ))
    assert result.social_activity_score == 0

def test_best_contact_priority():
    from leadforge_shared.scoring import ContactInput
    base = make_base_input()
    result = calculate_lead_score(ScoringInput(
        website_status=base.website_status,
        website=base.website,
        contacts=[ContactInput(type="PHONE"), ContactInput(type="EMAIL")],
        social_profiles=[],
        rating=None,
        review_count=None,
        has_phone=False,
        has_address=True,
    ))
    assert result.best_contact_method == "EMAIL"

def test_determinism():
    base = make_base_input()
    r1 = calculate_lead_score(base)
    r2 = calculate_lead_score(base)
    assert r1 == r2

def test_score_cap():
    from leadforge_shared.scoring import ContactInput, SocialProfileInput
    from datetime import datetime, timezone
    result = calculate_lead_score(ScoringInput(
        website_status="NOT_FOUND",
        website=None,
        contacts=[ContactInput(type="EMAIL"), ContactInput(type="WHATSAPP")],
        social_profiles=[
            SocialProfileInput(platform="FACEBOOK", last_activity_at=datetime.now(timezone.utc)),
            SocialProfileInput(platform="INSTAGRAM", last_activity_at=datetime.now(timezone.utc)),
        ],
        rating=4.5,
        review_count=500,
        has_phone=True,
        has_address=True,
    ))
    assert result.score <= 100
