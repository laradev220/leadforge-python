"""Contact extraction with rate-limited crawling via enhanced fetch_html.

Uses the shared fetch_html from base.py for retry, rate limiting, and caching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

import structlog
from leadforge_shared.utils import (
    is_valid_email,
    is_valid_phone,
    looks_like_phone,
    normalize_phone,
    region_for_url,
)
from selectolax.lexbor import LexborHTMLParser as HTMLParser

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
_PLACEHOLDER_EMAIL_DOMAINS = frozenset(
    {"example.com", "example.org", "example.net", "domain.com", "email.com"}
)
_TEL_LINK_RE = re.compile(r"""href=["']tel:([^"']+)["']""", re.IGNORECASE)
_IMAGE_EXT_RE = re.compile(r"\.(png|jpe?g|gif|webp|svg|avif|ico|bmp|css|js)$", re.IGNORECASE)


async def extract_contacts(
    html: str, base_url: str, region: str | None = None
) -> list[ExtractedContact]:
    """Extract contact information from HTML page content.

    ``region`` is an ISO-3166-1 alpha-2 code used to parse national phone
    formats; it defaults to the ccTLD of ``base_url`` when omitted.
    """
    resolved_region = region or region_for_url(base_url)
    contacts: list[ExtractedContact] = []
    seen: set[str] = set()
    tree = HTMLParser(html)

    # Extract emails
    emails = EMAIL_RE.findall(html)
    for email in emails:
        if not is_valid_email(email) or email in seen:
            continue
        if _IMAGE_EXT_RE.search(email):
            continue
        seen.add(email)
        local, domain = email.split("@", 1)
        if domain.lower() in _PLACEHOLDER_EMAIL_DOMAINS:
            continue
        local = local.lower()
        is_high = local in HIGH_CONF_EMAILS
        is_biz = domain.lower() not in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
        score = 90 if is_high and is_biz else (60 if is_biz else 30)
        contacts.append(ExtractedContact("EMAIL", email, score))

    # Extract phones from visible text only: <script>/<style> content is full
    # of timestamps and tracking IDs that look like long digit runs.
    for tag in tree.css("script, style, noscript"):
        tag.decompose()
    text = tree.body.text() if tree.body else ""
    candidates = PHONE_RE.findall(text) + _TEL_LINK_RE.findall(html)
    for candidate in candidates:
        cleaned = candidate.strip()
        if cleaned in seen or not looks_like_phone(cleaned):
            continue
        if not is_valid_phone(cleaned, resolved_region):
            continue
        normalized = normalize_phone(cleaned, resolved_region)
        if normalized in seen:
            continue
        seen.update((cleaned, normalized))
        contacts.append(ExtractedContact("PHONE", normalized, 70))

    # Extract WhatsApp links (duplicate links are common in headers/footers)
    for number in WHATSAPP_RE.findall(html):
        value = f"https://wa.me/{number}"
        if value in seen:
            continue
        seen.add(value)
        contacts.append(ExtractedContact("WHATSAPP", value, 80))

    # Detect contact forms
    form = tree.css_first("form")
    if form is not None and form.attrs:
        action = form.attrs.get("action", "") or ""
        url = urljoin(base_url, action) if action else base_url
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
    return [urljoin(base_url, p) for p in paths]
