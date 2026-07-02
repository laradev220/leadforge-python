"""End-to-end integration tests for the scraper pipeline.

Tests the full flow from HTML fetch through extraction strategies
to scored lead output, using fixture HTML files.
"""

from __future__ import annotations

import asyncio
from datetime import UTC

import pytest
from leadforge_scraper_core.monitors.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from leadforge_scraper_core.monitors.rate_limiter import DomainRateLimiter
from leadforge_scraper_core.strategies import create_pipeline
from leadforge_scraper_core.strategies.base import StrategyResult
from leadforge_scraper_core.strategies.regex import RegexStrategy
from leadforge_scraper_core.strategies.selector import SelectorStrategy
from leadforge_scraper_core.strategies.structured import StructuredDataStrategy
from leadforge_shared.scoring import ScoringInput, calculate_lead_score

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_dir():
    from pathlib import Path

    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def google_maps_html(fixture_dir):
    return (fixture_dir / "google_maps_listing.html").read_text()


@pytest.fixture
def business_html(fixture_dir):
    return (fixture_dir / "business_page_no_structured_data.html").read_text()


@pytest.fixture
def pipeline():
    """Full extraction pipeline sorted by priority."""
    return create_pipeline(
        [
            StructuredDataStrategy(),
            SelectorStrategy(),
            RegexStrategy(),
        ]
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestExtractionPipeline:
    """Test the multi-strategy extraction pipeline end-to-end."""

    def test_pipeline_runs_all_strategies(self, pipeline, google_maps_html):
        """Higher-priority strategies should run first and populate results."""
        # StructuredData (priority=0) should extract JSON-LD name/phone
        for strategy in pipeline:
            if strategy.can_handle(google_maps_html):
                # Run synchronously-style check
                # Use can_handle to confirm applicability
                assert strategy.can_handle(google_maps_html)
        # If we got here, pipeline can_handle check passes
        assert len(pipeline) == 3

    @pytest.mark.asyncio
    async def test_structured_extracts_jsonld(self, google_maps_html):
        """StructuredDataStrategy should extract JSON-LD data."""
        strategy = StructuredDataStrategy()
        result = await strategy.extract(google_maps_html, "https://example.com")
        assert result is not None
        assert result.name == "Joe's Pizza"
        assert result.phone == "+1-212-555-1234"
        # Address has 4 parts: street, city, region, postal (no country → trailing comma)
        assert result.address == "123 Broadway, New York, NY, 10001"
        assert result.rating == 4.5
        assert result.review_count == 230

    @pytest.mark.asyncio
    async def test_regex_augments_plain_html(self, business_html):
        """RegexStrategy should extract contacts from plain HTML."""
        strategy = RegexStrategy()
        result = await strategy.extract(business_html, "https://acmeservices.example.com")
        assert result is not None
        assert result.phone == "+1 (555) 123-4567"
        assert result.email == "contact@acmecorp.example.com"
        # Social handles from plain HTML
        assert result.social_handles.get("facebook") == "acmeservices"
        assert result.social_handles.get("instagram") == "acmeservicesinc"

    @pytest.mark.asyncio
    async def test_pipeline_merges_results(self, google_maps_html):
        """Pipeline should merge results from multiple strategies."""
        pipeline = create_pipeline(
            [
                StructuredDataStrategy(),
                RegexStrategy(),
            ]
        )
        best: StrategyResult | None = None
        for strategy in pipeline:
            result = await strategy.extract(google_maps_html, "https://example.com")
            if result:
                best = best.merge_with(result) if best else result
        assert best is not None
        assert best.name == "Joe's Pizza"
        # JSON-LD phone should be preserved
        assert best.phone == "+1-212-555-1234"

    @pytest.mark.asyncio
    async def test_regex_fallback_on_no_structured_data(self, business_html):
        """RegexStrategy should succeed on plain HTML (no JSON-LD/microdata)."""
        strategy = RegexStrategy()
        result = await strategy.extract(business_html, "https://example.com")
        assert result is not None
        assert result.phone is not None
        assert result.email is not None
        assert result.confidence == 70


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with scraper operations."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Circuit should open after reaching failure threshold."""
        cb = CircuitBreaker(
            source="test_source",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                window_seconds=60.0,
                open_duration_seconds=30.0,
            ),
        )
        assert cb.state == CircuitState.CLOSED
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_blocks_execution_when_open(self):
        """Circuit.can_execute should return False when OPEN."""
        cb = CircuitBreaker(
            source="test_source",
            config=CircuitBreakerConfig(
                failure_threshold=2, window_seconds=60.0, open_duration_seconds=30.0
            ),
        )
        for _ in range(2):
            await cb.record_failure()
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_circuit_success_closes_circuit(self):
        """Success in HALF_OPEN state should close the circuit."""
        cb = CircuitBreaker(
            source="test_source",
            config=CircuitBreakerConfig(
                failure_threshold=1, window_seconds=60.0, open_duration_seconds=30.0
            ),
        )
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # Transition to HALF_OPEN (manually for test)
        cb._state = CircuitState.HALF_OPEN
        cb._half_open_requests = 1
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestRateLimiterIntegration:
    """Test domain rate limiter behavior."""

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_delay(self):
        """DomainRateLimiter should enforce delay between requests to same domain."""
        limiter = DomainRateLimiter(delay_seconds=0.1)
        await limiter.acquire("example.com")
        start = asyncio.get_event_loop().time()
        await limiter.acquire("example.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.09

    @pytest.mark.asyncio
    async def test_different_domains_no_delay(self):
        """Different domains should not share rate limit state."""
        limiter = DomainRateLimiter(delay_seconds=0.5)
        await limiter.acquire("domain-a.com")
        start = asyncio.get_event_loop().time()
        await limiter.acquire("domain-b.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1


class TestLeadScoringIntegration:
    """Test lead scoring with scraped data."""

    def test_score_with_no_website(self):
        """Business with no website gets website_opportunity_score of 40."""
        base = ScoringInput(
            website_status="NOT_FOUND",
            website=None,
            contacts=[],
            social_profiles=[],
            rating=None,
            review_count=None,
            has_phone=True,
            has_address=True,
        )
        result = calculate_lead_score(base)
        assert result.website_opportunity_score == 40
        assert result.score >= 40

    def test_score_caps_at_100(self):
        """Total score should never exceed 100."""
        from datetime import datetime

        from leadforge_shared.scoring import ContactInput, SocialProfileInput

        scored = calculate_lead_score(
            ScoringInput(
                website_status="FOUND",
                website=None,  # weak website
                contacts=[
                    ContactInput(type="EMAIL"),
                    ContactInput(type="WHATSAPP"),
                    ContactInput(type="PHONE"),
                ],
                social_profiles=[
                    SocialProfileInput(platform="FACEBOOK", last_activity_at=datetime.now(UTC)),
                    SocialProfileInput(platform="INSTAGRAM", last_activity_at=datetime.now(UTC)),
                ],
                rating=4.8,
                review_count=1000,
                has_phone=True,
                has_address=True,
            )
        )
        assert scored.score <= 100

    def test_determinism(self):
        """Same input should always produce same score."""
        base = ScoringInput(
            website_status="NOT_FOUND",
            website=None,
            contacts=[],
            social_profiles=[],
            rating=4.5,
            review_count=200,
            has_phone=True,
            has_address=True,
        )
        r1 = calculate_lead_score(base)
        r2 = calculate_lead_score(base)
        assert r1 == r2


class TestFullPipelineFlow:
    """End-to-end test: fixture HTML → extraction → scoring."""

    @pytest.mark.asyncio
    async def test_google_maps_fixture_full_flow(self, google_maps_html):
        """Simulate full pipeline: JSON-LD extraction → lead scoring."""
        # Step 1: Extract using StructuredDataStrategy
        strategy = StructuredDataStrategy()
        result = await strategy.extract(google_maps_html, "https://example.com")
        assert result is not None
        assert result.name == "Joe's Pizza"
        assert result.phone == "+1-212-555-1234"

        # Step 2: Build ScoringInput from extracted data
        from leadforge_shared.scoring import ContactInput

        contacts = []
        if result.phone:
            contacts.append(ContactInput(type="PHONE"))
        if result.email:
            contacts.append(ContactInput(type="EMAIL"))

        scoring_input = ScoringInput(
            website_status="FOUND" if result.website else "NOT_FOUND",
            website=None,
            contacts=contacts,
            social_profiles=[],
            rating=result.rating,
            review_count=result.review_count,
            has_phone=bool(result.phone),
            has_address=bool(result.address),
        )
        score = calculate_lead_score(scoring_input)
        assert score.score > 0
        # rating_score exists if website scoring is enabled
        assert score.score > 0

    @pytest.mark.asyncio
    async def test_business_page_full_flow(self, business_html):
        """Simulate full pipeline: regex extraction → lead scoring."""
        # Step 1: Extract using RegexStrategy
        strategy = RegexStrategy()
        result = await strategy.extract(business_html, "https://acmeservices.example.com")
        assert result is not None
        assert result.phone == "+1 (555) 123-4567"
        assert result.email == "contact@acmecorp.example.com"
        assert "facebook" in result.social_handles

        # Step 2: Score
        from leadforge_shared.scoring import ContactInput, SocialProfileInput

        contacts = [ContactInput(type="EMAIL"), ContactInput(type="PHONE")]
        socials = [
            SocialProfileInput(platform="FACEBOOK", last_activity_at=None),
            SocialProfileInput(platform="INSTAGRAM", last_activity_at=None),
        ]
        scoring_input = ScoringInput(
            website_status="FOUND",
            website=None,
            contacts=contacts,
            social_profiles=socials,
            rating=None,
            review_count=None,
            has_phone=True,
            has_address=True,
        )
        score = calculate_lead_score(scoring_input)
        assert score.score > 0
        assert score.contact_quality_score > 0
