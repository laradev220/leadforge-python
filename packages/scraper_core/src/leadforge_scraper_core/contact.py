"""Contact extraction with rate-limited crawling via enhanced fetch_html.

Uses the shared fetch_html from base.py for retry, rate limiting, and caching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog
from leadforge_shared.utils import is_valid_email, normalize_phone
from selectolax.parser import HTMLParser

from leadforge_scraper_core.base import fetch_html

logger = structlog.get_logger("scraper.contact")


@dataclass
class ExtractedContact:
    type: str
    value: str
    confidence_score: int
    source: str = "WEBSITE"


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"[\+]?[\d\s\-\(\)]{7,20}")
WHATSAPP_RE = re.compile(r"(?:wa\.me|whatsapp\.com)/(?:send\?phone=)?(\d+)", re.I)

HIGH_CONF_EMAILS = ["info", "hello", "contact", "support", "admin", "sales"]


async def extract_contacts(html: str, base_url: str) -> list[ExtractedContact]:
    """Extract contact information from HTML page content."""
    contacts: list[ExtractedContact] = []
    seen: set[str] = set()
    tree = HTMLParser(html)

    # Extract emails
    emails = EMAIL_RE.findall(html)
    for email in emails:
        if not is_valid_email(email) or email in seen:
            continue
        seen.add(email)
        local = email.split("@")[0].lower()
        is_high = local in HIGH_CONF_EMAILS
        domain = email.split("@")[1]
        is_biz = domain not in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
        score = 90 if is_high and is_biz else (60 if is_biz else 30)
        contacts.append(ExtractedContact("EMAIL", email, score))

    # Extract phones from visible text
    text = tree.body.text() if tree.body else ""
    phones = PHONE_RE.findall(text)
    for p in phones:
        cleaned = p.strip()
        if len(cleaned) < 7 or cleaned in seen:
            continue
        seen.add(cleaned)
        try:
            normalized = normalize_phone(cleaned)
            contacts.append(ExtractedContact("PHONE", normalized, 70))
        except Exception:
            continue

    # Extract WhatsApp links
    whatsapp = WHATSAPP_RE.findall(html)
    for w in whatsapp:
        contacts.append(ExtractedContact("WHATSAPP", f"https://wa.me/{w}", 80))

    # Detect contact forms
    form = tree.css_first("form")
    if form is not None and form.attrs:
        action = form.attrs.get("action", "") or ""
        url = f"{base_url}/{action.lstrip('/')}" if action else base_url
        contacts.append(ExtractedContact("CONTACT_FORM", url, 70))

    return contacts


async def crawl_website(url: str) -> str:
    """Crawl a website using the enhanced fetch_html with retry, rate limiting, and caching."""
    if not url:
        logger.warning("crawl_website.empty_url")
        return ""
    html = await fetch_html(
        url,
        use_playwright=False,
        source="contact_crawl",
    )
    return html or ""


def get_priority_urls(base_url: str) -> list[str]:
    """Return priority page URLs for contact extraction."""
    paths = ["/contact", "/about", "/contact-us", "/about-us", "/team", "/support"]
    from urllib.parse import urljoin

    return [urljoin(base_url, p) for p in paths]
