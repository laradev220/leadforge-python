"""Unit tests for social crawling fixes.

Tests for the critical bugs fixed in the social crawling functionality:
1. Email extraction logic fix
2. Phone number validation fix
3. Error handling improvements
4. Platform definitions centralization
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from leadforge_scraper_core.social import scrape_social_profile_for_contacts
from leadforge_scraper_core.social_platforms import (
    get_social_platform_search_terms,
    is_business_email,
    is_valid_phone_number,
)


class TestBusinessEmailDetection:
    """Tests for business email detection logic."""

    def test_business_email_detection(self):
        """Test that business emails are correctly identified."""
        # Business-like domains
        assert is_business_email("contact@company.com")
        assert is_business_email("sales@acme.com")
        assert is_business_email("info@business.co.uk")

        # Free domains with business indicators
        assert is_business_email("info@gmail.com")
        assert is_business_email("contact@yahoo.com")
        assert is_business_email("support@hotmail.com")

        # Free domains without business indicators
        assert not is_business_email("john.doe@gmail.com")
        assert not is_business_email("user@yahoo.com")

        # Generic/system emails
        assert not is_business_email("noreply@company.com")
        assert not is_business_email("test@example.com")
        assert is_business_email("info@acme.com")  # info is business indicator

        # Other domains (org, net, etc.)
        assert is_business_email("contact@company.org")
        assert is_business_email("info@business.net")

    def test_invalid_emails(self):
        """Test that invalid emails are rejected."""
        assert not is_business_email("")
        assert not is_business_email("invalid-email")
        assert not is_business_email("@example.com")
        assert not is_business_email("user@")


class TestPhoneNumberValidation:
    """Tests for phone number validation."""

    def test_valid_phone_numbers(self):
        """Test that valid phone numbers are accepted."""
        assert is_valid_phone_number("+1-555-123-4567")
        assert is_valid_phone_number("(555) 987-6543")
        assert is_valid_phone_number("555-123-4567")
        assert is_valid_phone_number("+44 20 7946 0958")
        assert is_valid_phone_number("123-456-7890")

    def test_invalid_phone_numbers(self):
        """Test that invalid phone numbers are rejected."""
        assert not is_valid_phone_number("")
        assert not is_valid_phone_number("123-456")  # Too short
        assert not is_valid_phone_number("123-456-7890-123-456")  # Too long
        assert not is_valid_phone_number("Order #123-456-789")  # Contains order number
        assert not is_valid_phone_number("abc-def-ghi")  # Not a phone number

    def test_phone_number_formatting(self):
        """Test various phone number formats."""
        formats = [
            "+1 (555) 123-4567",
            "555-123-4567",
            "(555) 987-6543",
            "+44 20 7946 0958",
            "123 456 7890",
            "+1-800-555-1234",
        ]

        for phone in formats:
            assert is_valid_phone_number(phone)


class TestSocialPlatformDefinitions:
    """Tests for centralized social platform definitions."""

    def test_social_platform_search_terms(self):
        """Test that social platform search terms are correctly defined."""
        terms = get_social_platform_search_terms()

        # Should contain all expected platforms
        expected_platforms = [
            "linkedin",
            "facebook",
            "instagram",
            "twitter",
            "tiktok",
            "threads",
            "youtube",
            "x",
        ]

        for platform in expected_platforms:
            assert platform in terms

        # Should not contain duplicates
        assert len(terms) == len(set(terms))

    def test_social_platform_search_terms_order(self):
        """Test that social platform search terms are in a logical order."""
        terms = get_social_platform_search_terms()

        # Should start with major platforms
        assert terms[0] == "linkedin"
        assert terms[1] == "facebook"
        assert terms[2] == "instagram"


class TestSocialCrawlingFixes:
    """Integration tests for social crawling fixes."""

    @pytest.mark.asyncio
    async def test_email_extraction_fix(self):
        """Test that email extraction fix works correctly."""
        html = """
        <html>
            <body>
                <p>Contact: business@company.com</p>
                <p>Sales: sales@acme.com</p>
                <p>Support: support@acme.co.uk</p>
                <p>Info: info@gmail.com</p>
                <p>Admin: admin@yahoo.com</p>
                <p>Invalid: noreply@company.com</p>
            </body>
        </html>
        """

        with patch("leadforge_scraper_core.base.fetch_html", return_value=html):
            result = await scrape_social_profile_for_contacts("https://example.com", "FACEBOOK")

            # Should include business@company.com, sales@acme.com, support@acme.co.uk
            # Should NOT include info@gmail.com, admin@yahoo.com (free domains without business indicators)
            # Should NOT include noreply@company.com (generic email)
            assert "public_email" in result
            assert result["public_email"] in [
                "business@company.com",
                "sales@acme.com",
                "support@acme.co.uk",
            ]

    @pytest.mark.asyncio
    async def test_phone_extraction_fix(self):
        """Test that phone extraction fix works correctly."""
        html = """
        <html>
            <body>
                <p>Business: +1-555-123-4567</p>
                <p>Office: (555) 987-6543</p>
                <p>Mobile: 555-123-4567</p>
                <p>Invalid: 123-456</p>
                <p>Order: Order #123-456-789</p>
                <p>Not a phone: abc-def-ghi</p>
            </body>
        </html>
        """

        with patch("leadforge_scraper_core.base.fetch_html", return_value=html):
            result = await scrape_social_profile_for_contacts("https://example.com", "FACEBOOK")

            # Should include valid phone numbers (normalized)
            # Should NOT include invalid ones like "123-456" or "Order #123-456-789"
            assert "public_phone" in result
            assert result["public_phone"] in ["+15551234567", "15559876543", "15551234567"]

    @pytest.mark.asyncio
    async def test_social_worker_error_handling(self):
        """Test social worker error handling improvements."""
        from leadforge_shared.types import SocialJobData
        from leadforge_social_worker.main import social_processor

        # Mock data
        data = SocialJobData(
            business_id="550e8400-e29b-41d4-a716-446655440000", website_url="https://example.com"
        )
        logger = MagicMock()

        # Mock the internal HTTP fetch to raise an exception
        with patch(
            "leadforge_scraper_core.base.fetch_html", side_effect=Exception("Crawl failed")
        ):
            with patch("leadforge_social_worker.main._search_social_by_name", return_value=[]):
                with patch("leadforge_social_worker.main.get_session_ctx") as mock_session:
                    mock_business = MagicMock()
                    mock_business.name = "Test Business"
                    mock_session.return_value.__aenter__.return_value.execute.return_value.scalar_one_or_none.return_value = mock_business

                    # Should not raise exception, should handle gracefully
                    await social_processor(data, logger)

                    # Verify error was logged (crawl failed)
                    logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_social_platform_centralization(self):
        """Test that social platform definitions are centralized."""
        from leadforge_scraper_core.social_platforms import SOCIAL_DOMAINS

        # Verify that SOCIAL_DOMAINS is used consistently
        assert "facebook.com" in SOCIAL_DOMAINS
        assert "instagram.com" in SOCIAL_DOMAINS
        assert "linkedin.com" in SOCIAL_DOMAINS
        assert "youtube.com" in SOCIAL_DOMAINS
        assert "tiktok.com" in SOCIAL_DOMAINS
        assert "twitter.com" in SOCIAL_DOMAINS
        assert "x.com" in SOCIAL_DOMAINS

        # Verify that all platforms have valid enum values
        from leadforge_shared.types import SocialPlatform

        for _domain, platform in SOCIAL_DOMAINS.items():
            assert isinstance(platform, SocialPlatform)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
