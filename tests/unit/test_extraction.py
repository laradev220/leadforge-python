"""Unit tests for contact extraction. Ported from tests/unit/extraction.test.ts."""

import pytest
from leadforge_scraper_core.contact import extract_contacts, is_valid_email, normalize_phone
from leadforge_shared.utils import extract_domain

HTML_FIXTURE = """
<html>
  <body>
    <p>Email: info@acme.com</p>
    <p>Email: support@business.com</p>
    <p>Phone: (415) 555-0100</p>
    <p>Phone: +1 415 555 0199</p>
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
    info_email = next((c for c in contacts if c.value == "info@acme.com"), None)
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
    assert normalize_phone("(415) 555-0100") == "+14155550100"
    assert normalize_phone("+923001234567") == "+923001234567"


def test_domain_extraction():
    assert extract_domain("https://www.example.com/page") == "example.com"
    assert extract_domain("not-a-url") is None


async def test_contact_extraction_rejects_junk_and_uses_tel_links() -> None:
    html = """
    <html><body>
      <p>10 10 0 0 0 22 12</p>
      <p>Call us: 0332 9307688</p>
      <a href="tel:03329307688">Call</a>
      <a href="mailto:info@clinic.pk">Email</a>
      <p>you@example.com</p>
    </body></html>
    """

    contacts = await extract_contacts(html, "https://clinic.pk")

    phones = {c.value for c in contacts if c.type == "PHONE"}
    emails = {c.value for c in contacts if c.type == "EMAIL"}

    assert phones == {"+923329307688"}
    assert "info@clinic.pk" in emails
    assert "you@example.com" not in emails


async def test_image_filenames_are_not_emails() -> None:
    html = """
    <html><body>
      <img src="cropped-Logo_Alt01@300x-32x32.png">
      <p>Email: info@clinic.pk</p>
    </body></html>
    """
    contacts = await extract_contacts(html, "https://clinic.pk")
    emails = {c.value for c in contacts if c.type == "EMAIL"}
    assert emails == {"info@clinic.pk"}


async def test_whatsapp_links_are_deduplicated() -> None:
    html = '<html><body><a href="https://wa.me/923001234567">a</a>' * 3 + "</body></html>"
    contacts = await extract_contacts(html, "https://clinic.pk")
    whatsapp = [c for c in contacts if c.type == "WHATSAPP"]
    assert len(whatsapp) == 1
