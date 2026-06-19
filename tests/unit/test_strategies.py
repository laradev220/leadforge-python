"""Unit tests for extraction strategies."""

from __future__ import annotations

import pytest

from leadforge_scraper_core.strategies.base import StrategyResult, create_pipeline, ExtractionStrategy
from leadforge_scraper_core.strategies.structured import StructuredDataStrategy
from leadforge_scraper_core.strategies.selector import SelectorStrategy
from leadforge_scraper_core.strategies.regex import RegexStrategy


@pytest.fixture
def google_maps_html() -> str:
    from pathlib import Path
    fixture = Path(__file__).parent.parent / "fixtures" / "google_maps_listing.html"
    return fixture.read_text()


@pytest.fixture
def yelp_html() -> str:
    from pathlib import Path
    fixture = Path(__file__).parent / "fixtures" / "yelp_search.html"
    return fixture.read_text()


@pytest.fixture
def plain_html() -> str:
    from pathlib import Path
    fixture = Path(__file__).parent / "fixtures" / "business_page_no_structured_data.html"
    return fixture.read_text()


class TestStructuredDataStrategy:
    """Tests for StructuredDataStrategy — JSON-LD, microdata, Open Graph extraction."""

    def test_can_handle_jsonld(self, google_maps_html: str) -> None:
        strategy = StructuredDataStrategy()
        assert strategy.can_handle(google_maps_html) is True

    def test_cannot_handle_plain_html(self, plain_html: str) -> None:
        strategy = StructuredDataStrategy()
        assert strategy.can_handle(plain_html) is False

    @pytest.mark.asyncio
    async def test_extracts_jsonld(self, google_maps_html: str) -> None:
        strategy = StructuredDataStrategy()
        result = await strategy.extract(google_maps_html, "https://example.com")
        assert result is not None
        assert result.name == "Joe's Pizza"
        assert result.phone == "+1-212-555-1234"
        assert result.address == "123 Broadway, New York, NY, 10001"  # country omitted in fixture
        assert result.rating == 4.5
        assert result.review_count == 230
        assert result.website == "https://joespizza.com"
        assert result.confidence == 95

    @pytest.mark.asyncio
    async def test_extracts_open_graph(self, google_maps_html: str) -> None:
        strategy = StructuredDataStrategy()
        result = await strategy.extract(google_maps_html, "https://example.com")
        assert result is not None
        assert result.website == "https://joespizza.com"  # from OG

    @pytest.mark.asyncio
    async def test_returns_none_when_no_data(self, plain_html: str) -> None:
        strategy = StructuredDataStrategy()
        result = await strategy.extract(plain_html, "https://example.com")
        assert result is None


class TestRegexStrategy:
    """Tests for RegexStrategy — email, phone, social handle extraction."""

    def test_can_handle(self, plain_html: str) -> None:
        strategy = RegexStrategy()
        assert strategy.can_handle(plain_html) is True

    @pytest.mark.asyncio
    async def test_extracts_emails(self, plain_html: str) -> None:
        strategy = RegexStrategy()
        result = await strategy.extract(plain_html, "https://example.com")
        assert result is not None
        assert result.email == "contact@acmecorp.example.com"
        assert "all_emails" in result.extras

    @pytest.mark.asyncio
    async def test_extracts_phones(self, plain_html: str) -> None:
        strategy = RegexStrategy()
        result = await strategy.extract(plain_html, "https://example.com")
        assert result is not None
        assert result.phone == "+1 (555) 123-4567"
        assert "all_phones" in result.extras

    @pytest.mark.asyncio
    async def test_extracts_social_handles(self, plain_html: str) -> None:
        strategy = RegexStrategy()
        result = await strategy.extract(plain_html, "https://example.com")
        assert result is not None
        # Handles deduplicated across platforms — same handle string on multiple
        # platforms only stores the first one (e.g. "acmeservices" on both Facebook
        # and LinkedIn → only Facebook wins). Instagram handle is unique so it's stored.
        assert "facebook" in result.social_handles
        assert "instagram" in result.social_handles
        # LinkedIn handle "acmeservices" is same as Facebook handle → skipped
        # (LinkedIn would be present if it had a different handle, e.g. /in/acme-profile)

    @pytest.mark.asyncio
    async def test_deduplicates_emails(self) -> None:
        # Use emails that pass the discard filter (no 'noreply', 'test', 'example' prefix)
        html = "<p>alice@business.example.com</p><p>alice@business.example.com</p><p>bob@corp.example.com</p>"
        strategy = RegexStrategy()
        result = await strategy.extract(html, "https://example.com")
        assert result is not None
        emails = result.extras.get("all_emails", [])
        assert len([e for e in emails if "alice" in e.lower()]) == 1

    @pytest.mark.asyncio
    async def test_discards_freemail_domains(self) -> None:
        html = "<p>john.doe@gmail.com</p><p>contact@acmecorp.example.com</p>"
        strategy = RegexStrategy()
        result = await strategy.extract(html, "https://example.com")
        assert result is not None
        assert result.email == "contact@acmecorp.example.com"
        # Gmail should be discarded
        emails = result.extras.get("all_emails", [])
        assert not any("gmail" in e for e in emails)


class TestStrategyResult:
    """Tests for StrategyResult merging and confidence."""

    def test_merge_prefers_non_none(self) -> None:
        r1 = StrategyResult(name="Test Business", phone=None, strategy_name="s1")
        r2 = StrategyResult(name=None, phone="+1-555-1234", strategy_name="s2")
        merged = r1.merge_with(r2)
        assert merged.name == "Test Business"
        assert merged.phone == "+1-555-1234"

    def test_merge_uses_higher_confidence(self) -> None:
        r1 = StrategyResult(confidence=50, strategy_name="s1")
        r2 = StrategyResult(confidence=90, strategy_name="s2")
        merged = r1.merge_with(r2)
        assert merged.confidence == 90


class TestPipeline:
    """Tests for extraction pipeline ordering."""

    def test_pipeline_sorted_by_priority(self) -> None:
        from unittest.mock import MagicMock

        mock1 = MagicMock()
        mock1.name = "first"
        mock1.priority = 20
        mock1.can_handle.return_value = True
        mock1.extract.return_value = StrategyResult(strategy_name="first")

        mock2 = MagicMock()
        mock2.name = "second"
        mock2.priority = 5
        mock2.can_handle.return_value = True
        mock2.extract.return_value = StrategyResult(strategy_name="second")

        pipeline = create_pipeline([mock1, mock2])
        assert pipeline[0].priority < pipeline[1].priority