"""Unit tests for contact extraction. Ported from tests/unit/extraction.test.ts."""

import pytest
from leadforge_scraper_core.contact import extract_contacts, normalize_phone, is_valid_email
from leadforge_shared.utils import extract_domain

HTML_FIXTURE = """
<html>
  <body>
    <p>Email: info@example.com</p>
    <p>Email: support@business.com</p>
    <p>Phone: (555) 123-4567</p>
    <p>Phone: +1 555-987-6543</p>
    <a href="https://wa.me/1234567890">WhatsApp</a>
    <form action="/contact">
      <input name="email" />
      <textarea name="message"></textarea>
    </form>
  </body>
</html>
"""

@pytest.mark.asyncio
async def test_extract_emails():
    contacts = await extract_contacts(HTML_FIXTURE, "https://example.com")
    emails = [c for c in contacts if c.type == "EMAIL"]
    assert len(emails) >= 1

@pytest.mark.asyncio
async def test_high_confidence_email():
    contacts = await extract_contacts(HTML_FIXTURE, "https://example.com")
    info_email = next((c for c in contacts if c.value == "info@example.com"), None)
    assert info_email is not None
    assert info_email.confidence_score >= 70  # RegexStrategy returns confidence=70

@pytest.mark.asyncio
async def test_extract_phones():
    contacts = await extract_contacts(HTML_FIXTURE, "https://example.com")
    phones = [c for c in contacts if c.type == "PHONE"]
    assert len(phones) >= 1

@pytest.mark.asyncio
async def test_detect_contact_form():
    contacts = await extract_contacts(HTML_FIXTURE, "https://example.com")
    forms = [c for c in contacts if c.type == "CONTACT_FORM"]
    assert len(forms) >= 1

@pytest.mark.asyncio
async def test_extract_whatsapp():
    contacts = await extract_contacts(HTML_FIXTURE, "https://example.com")
    whatsapp = [c for c in contacts if c.type == "WHATSAPP"]
    assert len(whatsapp) >= 1

def test_email_validation():
    assert is_valid_email("test@example.com")
    assert is_valid_email("info@business.co.uk")
    assert not is_valid_email("not-an-email")
    assert not is_valid_email("@example.com")
    assert not is_valid_email("")

def test_phone_normalization():
    assert normalize_phone("(555) 123-4567") == "+15551234567"
    assert normalize_phone("+923001234567") == "+923001234567"

def test_domain_extraction():
    assert extract_domain("https://www.example.com/page") == "example.com"
    assert extract_domain("not-a-url") is None
