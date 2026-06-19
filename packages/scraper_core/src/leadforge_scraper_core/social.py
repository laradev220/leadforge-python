"""Social profile discovery and scraping. Mirrors packages/scraper-core/src/social.ts.

Enhanced with profile-scraping capabilities so social profile pages (LinkedIn,
Facebook, Instagram, etc.) can be scraped for public contact info (email, phone,
website) — especially important for businesses without their own website.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import structlog
from selectolax.parser import HTMLParser

from leadforge_scraper_core.base import fetch_html
from leadforge_shared.types import SocialPlatform
from leadforge_shared.utils import normalize_phone, is_valid_email
from leadforge_scraper_core.social_platforms import (
    SOCIAL_DOMAINS,
    is_business_email,
    is_valid_phone_number,
)

logger = structlog.get_logger("scraper.social")

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Improved phone regex - more specific and valid
PHONE_RE = re.compile(
    r"""
    (?:\+?[1-9]\d{0,2}[\s.-]?)?    # optional country code e.g. +1
    \(?[2-9]\d{2}\)?                # area code with optional parens e.g. (555)
    [\s.-]*                         # separator
    \d{3}                           # first 3 digits
    [\s.-]*                         # separator
    \d{4}                           # last 4 digits
    |
    \+[1-9]\s?\d\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}
    """,
    re.VERBOSE,
)

# Domains to skip when extracting website links from profile pages.
# These are social/platform domains, not the business's own website.
_SKIP_WEBSITE_DOMAINS: frozenset[str] = frozenset({
    "facebook.com", "fb.com", "instagram.com", "linkedin.com",
    "twitter.com", "x.com", "tiktok.com", "youtube.com",
    "google.com", "accounts.google.com", "wa.me", "api.whatsapp.com",
    "snapchat.com", "pinterest.com", "reddit.com", "medium.com",
})


@dataclass
class ExtractedSocial:
    platform: SocialPlatform
    profile_url: str
    username: str | None = None
    confidence_score: int = 70


async def extract_social_profiles(html: str, base_url: str) -> list[ExtractedSocial]:
    """Extract social profile links from HTML page content."""
    profiles = []
    seen = set()
    tree = HTMLParser(html)

    for a in tree.css("a[href]"):
        href = a.attrs.get("href", "")
        if not href:
            continue
        try:
            from urllib.parse import urlparse, urljoin
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            domain = parsed.netloc.removeprefix("www.")
            platform = SOCIAL_DOMAINS.get(domain)
            if not platform or full_url in seen:
                continue
            seen.add(full_url)

            username = parsed.path.split("/")[-1] or None
            profiles.append(ExtractedSocial(platform, full_url, username))
        except Exception:
            continue

    for meta in tree.css('meta[property^="og:"], meta[name^="twitter:"]'):
        content = meta.attrs.get("content", "")
        if not content or not content.startswith("http"):
            continue
        try:
            from urllib.parse import urlparse
            parsed = urlparse(content)
            domain = parsed.netloc.removeprefix("www.")
            platform = SOCIAL_DOMAINS.get(domain)
            if not platform or content in seen:
                continue
            seen.add(content)
            profiles.append(ExtractedSocial(platform, content))
        except Exception:
            continue

    return profiles


async def scrape_social_profile_for_contacts(
    profile_url: str,
    platform: str,
) -> dict[str, Any]:
    """Scrape a social profile page for public contact information.

    Visits the profile page using Playwright (social sites are JS-heavy)
    and extracts emails, phone numbers, and website links from the
    rendered page content.

    Args:
        profile_url: Full URL to the social profile (e.g. LinkedIn company page,
                    Facebook business page, Instagram profile).
        platform: Platform name (FACEBOOK, INSTAGRAM, LINKEDIN, TWITTER, etc.).

    Returns:
        Dict with keys: public_email, public_phone, website (all optional).
        Returns empty dict if scraping fails or no contacts found.
    """
    result: dict[str, Any] = {}

    if not profile_url:
        return result

    log = logger.bind(platform=platform, url=profile_url)

    try:
        # Use Playwright for JS-heavy social media pages
        html = await fetch_html(
            profile_url,
            use_playwright=True,
            source="social_scraper",
            logger=log,
        )

        if not html or len(html) < 200:
            log.debug("social_scrape.empty_or_blocked")
            return result

        tree = HTMLParser(html)

        # ── Extract email ──────────────────────────────────────────────────
        emails = [e for e in EMAIL_RE.findall(html) if is_valid_email(e)]
        # Prefer business email, fallback to any valid
        for email in emails:
            if is_business_email(email):
                result["public_email"] = email
                break
        if "public_email" not in result and emails:
            result["public_email"] = emails[0]

        # ── Extract phone ──────────────────────────────────────────────────
        text = tree.body.text() if tree.body else ""
        phones = PHONE_RE.findall(text)
        for p in phones:
            cleaned = p.strip()
            if len(cleaned) < 7:
                continue
                
            # Use centralized phone validation
            if not is_valid_phone_number(cleaned):
                continue
                
            try:
                phone = normalize_phone(cleaned)
                result["public_phone"] = phone
                break
            except Exception:
                continue

        # ── Extract website link ───────────────────────────────────────────
        from urllib.parse import urlparse

        for a in tree.css("a[href]"):
            href = a.attrs.get("href", "")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            try:
                # Resolve relative URLs
                from urllib.parse import urljoin
                full_href = urljoin(profile_url, href)
                parsed = urlparse(full_href)
                domain = parsed.netloc.removeprefix("www.").lower()

                # Must look like a real website
                if (
                    domain
                    and "." in domain
                    and domain not in _SKIP_WEBSITE_DOMAINS
                    and not any(d in domain for d in ["google.com", "fb.com"])
                    and parsed.scheme in ("http", "https")
                ):
                    # Give extra weight to links explicitly labelled as website/email
                    link_text = (a.text() or "").strip().lower()
                    if any(k in link_text for k in ["website", "site", "web", "business site"]):
                        result["website"] = full_href
                        break
                    # For LinkedIn, take the first non-social link as the website
                    if platform == "LINKEDIN" and "website" not in result:
                        result["website"] = full_href
                        break
            except Exception:
                continue

        if result:
            log.info(
                "social_scrape.found_contacts",
                has_email="public_email" in result,
                has_phone="public_phone" in result,
                has_website="website" in result,
            )

    except Exception as exc:
        log.debug("social_scrape.failed", error=str(exc))

    return result
