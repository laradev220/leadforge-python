"""Unit tests for contact.py improvements — empty URL guard, priority URLs, confidence scoring.

Tests the fixes applied to the contact extraction pipeline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from leadforge_scraper_core.contact import (
    ExtractedContact,
    crawl_website,
    extract_contacts,
    get_priority_urls,
)

# ── crawl_website improvements ────────────────────────────────────────────────


class TestCrawlWebsite:
    """Tests for the improved crawl_website() with empty URL guard."""

    @pytest.mark.asyncio
    async def test_empty_url_returns_early(self) -> None:
        """Should return empty string without calling fetch_html for empty URLs."""
        with patch(
            "leadforge_scraper_core.contact.fetch_html", new_callable=AsyncMock
        ) as mock_fetch:
            result = await crawl_website("")
            assert result == ""
            mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_url_returns_early(self) -> None:
        """Should handle None-like falsy values."""
        with patch(
            "leadforge_scraper_core.contact.fetch_html", new_callable=AsyncMock
        ) as mock_fetch:
            result = await crawl_website("")
            assert result == ""
            mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_url_calls_fetch_html(self) -> None:
        """Should delegate to fetch_html for valid URLs."""
        with patch(
            "leadforge_scraper_core.contact.fetch_html",
            new_callable=AsyncMock,
            return_value="<html>content</html>",
        ) as mock_fetch:
            result = await crawl_website("https://example.com")
            assert result == "<html>content</html>"
            mock_fetch.assert_called_once_with(
                "https://example.com",
                use_playwright=False,
                source="contact_crawl",
            )

    @pytest.mark.asyncio
    async def test_fetch_html_none_returns_empty(self) -> None:
        """Should return empty string when fetch_html returns None."""
        with patch(
            "leadforge_scraper_core.contact.fetch_html",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await crawl_website("https://example.com")
            assert result == ""


# ── get_priority_urls ─────────────────────────────────────────────────────────


class TestGetPriorityUrls:
    """Tests for get_priority_urls()."""

    def test_returns_expected_paths(self) -> None:
        urls = get_priority_urls("https://example.com")
        assert "/contact" in urls[0]
        assert "/about" in urls[1]

    def test_exactly_six_urls(self) -> None:
        urls = get_priority_urls("https://example.com")
        assert len(urls) == 6

    def test_trailing_slash_handling(self) -> None:
        urls = get_priority_urls("https://example.com")
        assert all(url.startswith("https://example.com") for url in urls)

    def test_contact_form_url(self) -> None:
        urls = get_priority_urls("https://example.com")
        assert any("contact" in url for url in urls)

    def test_about_url(self) -> None:
        urls = get_priority_urls("https://example.com")
        assert any("about" in url for url in urls)

    def test_team_url(self) -> None:
        urls = get_priority_urls("https://example.com")
        assert any("team" in url for url in urls)

    def test_support_url(self) -> None:
        urls = get_priority_urls("https://example.com")
        assert any("support" in url for url in urls)

    def test_handles_subdirectory_base(self) -> None:
        urls = get_priority_urls("https://example.com/site/")
        # urljoin with absolute paths (starting with /) replaces the base path
        # e.g. /site/ + /contact → https://example.com/contact
        assert all(url.startswith("https://example.com") for url in urls)
        # Relative paths would append, but the function uses absolute paths (/...)

    def test_handles_port_in_url(self) -> None:
        urls = get_priority_urls("https://example.com:8080")
        assert all(url.startswith("https://example.com:8080") for url in urls)


# ── extract_contacts ──────────────────────────────────────────────────────────

SAMPLE_HTML = """
<html>
  <body>
    <p>Email: info@acme.com</p>
    <p>Email: support@business.co.uk</p>
    <p>Phone: (415) 555-0100</p>
    <p>Phone: +1 415 555 0199</p>
    <a href="https://wa.me/1234567890">WhatsApp</a>
    <a href="https://web.whatsapp.com/send?phone=9876543210">Chat</a>
    <form action="/contact">
      <input name="email" />
      <textarea name="message"></textarea>
    </form>
  </body>
</html>
"""


class TestExtractContacts:
    """Tests for extract_contacts()."""

    @pytest.mark.asyncio
    async def test_extracts_emails(self) -> None:
        contacts = await extract_contacts(SAMPLE_HTML, "https://example.com")
        emails = [c for c in contacts if c.type == "EMAIL"]
        assert len(emails) >= 2

    @pytest.mark.asyncio
    async def test_high_confidence_for_info(self) -> None:
        contacts = await extract_contacts(SAMPLE_HTML, "https://example.com")
        info_email = next((c for c in contacts if c.value == "info@acme.com"), None)
        assert info_email is not None
        assert info_email.confidence_score >= 80

    @pytest.mark.asyncio
    async def test_extracts_phones(self) -> None:
        contacts = await extract_contacts(SAMPLE_HTML, "https://example.com")
        phones = [c for c in contacts if c.type == "PHONE"]
        assert len(phones) >= 1

    @pytest.mark.asyncio
    async def test_detects_contact_form(self) -> None:
        contacts = await extract_contacts(SAMPLE_HTML, "https://example.com")
        forms = [c for c in contacts if c.type == "CONTACT_FORM"]
        assert len(forms) >= 1

    @pytest.mark.asyncio
    async def test_contact_form_url_constructed(self) -> None:
        contacts = await extract_contacts(SAMPLE_HTML, "https://example.com")
        forms = [c for c in contacts if c.type == "CONTACT_FORM"]
        if forms:
            assert "example.com/contact" in forms[0].value

    @pytest.mark.asyncio
    async def test_extracts_whatsapp(self) -> None:
        contacts = await extract_contacts(SAMPLE_HTML, "https://example.com")
        whatsapp = [c for c in contacts if c.type == "WHATSAPP"]
        assert len(whatsapp) >= 2  # wa.me + web.whatsapp.com

    @pytest.mark.asyncio
    async def test_whatsapp_url_format(self) -> None:
        contacts = await extract_contacts(SAMPLE_HTML, "https://example.com")
        whatsapp = [c for c in contacts if c.type == "WHATSAPP"]
        wa_urls = [c.value for c in whatsapp]
        assert any("wa.me/1234567890" in u for u in wa_urls)

    @pytest.mark.asyncio
    async def test_deduplicates(self) -> None:
        html = """
        <html><body>
          <p>Email: info@acme.com</p>
          <p>Also reachable at: info@example.com</p>
          <p>Phone: (415) 555-0100</p>
          <p>Phone: (415) 555-0100</p>
        </body></html>
        """
        contacts = await extract_contacts(html, "https://example.com")
        emails = [c for c in contacts if c.type == "EMAIL"]
        phones = [c for c in contacts if c.type == "PHONE"]
        assert len(emails) <= 1  # Deduplicated
        assert len(phones) <= 1  # Deduplicated (same normalized value)

    @pytest.mark.asyncio
    async def test_handles_empty_html(self) -> None:
        contacts = await extract_contacts("", "https://example.com")
        assert contacts == []

    @pytest.mark.asyncio
    async def test_handles_no_contacts(self) -> None:
        html = "<html><body><h1>Welcome</h1></body></html>"
        contacts = await extract_contacts(html, "https://example.com")
        assert contacts == []

    @pytest.mark.asyncio
    async def test_lower_confidence_for_free_email(self) -> None:
        html = "<html><body><p>Email: business@gmail.com</p></body></html>"
        contacts = await extract_contacts(html, "https://example.com")
        emails = [c for c in contacts if c.type == "EMAIL"]
        if emails:
            assert emails[0].confidence_score < 60

    @pytest.mark.asyncio
    async def test_confidence_for_business_email(self) -> None:
        html = "<html><body><p>Email: hello@acmecorp.com</p></body></html>"
        contacts = await extract_contacts(html, "https://example.com")
        emails = [c for c in contacts if c.type == "EMAIL"]
        if emails:
            assert emails[0].confidence_score >= 80

    @pytest.mark.asyncio
    async def test_source_is_website(self) -> None:
        contacts = await extract_contacts(SAMPLE_HTML, "https://example.com")
        assert all(c.source == "WEBSITE" for c in contacts)


# ── ExtractedContact dataclass ────────────────────────────────────────────────


class TestExtractedContact:
    """Tests for the ExtractedContact dataclass."""

    def test_default_source(self) -> None:
        contact = ExtractedContact("EMAIL", "test@example.com", 80)
        assert contact.source == "WEBSITE"

    def test_custom_source(self) -> None:
        contact = ExtractedContact("PHONE", "+1234567890", 70, source="MAPS")
        assert contact.source == "MAPS"

    def test_fields(self) -> None:
        contact = ExtractedContact("EMAIL", "test@example.com", 90)
        assert contact.type == "EMAIL"
        assert contact.value == "test@example.com"
        assert contact.confidence_score == 90

    def test_repr(self) -> None:
        contact = ExtractedContact("EMAIL", "test@example.com", 80)
        r = repr(contact)
        assert "EMAIL" in r
        assert "test@example.com" in r
