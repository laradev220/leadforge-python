"""Social profile discovery and scraping.

Enhanced with rich profile data extraction (followers, bio, posts, etc.)
and contact info extraction (email, phone, website).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import structlog
from leadforge_shared.dates import parse_iso_datetime, parse_relative_phrase
from leadforge_shared.types import SocialPlatform
from leadforge_shared.utils import is_valid_email, normalize_phone
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from leadforge_scraper_core.social_platforms import (
    SOCIAL_DOMAINS,
    is_business_email,
    is_valid_phone_number,
)

logger = structlog.get_logger("scraper.social")

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

PHONE_RE = re.compile(
    r"""
    (?:\+?[1-9]\d{0,2}[\s.-]?)?
    \(?[2-9]\d{2}\)?
    [\s.-]*
    \d{3}
    [\s.-]*
    \d{4}
    |
    \+[1-9]\s?\d\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}
    """,
    re.VERBOSE,
)

_SKIP_WEBSITE_DOMAINS: frozenset[str] = frozenset(
    {
        "facebook.com",
        "fb.com",
        "instagram.com",
        "linkedin.com",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "youtube.com",
        "google.com",
        "accounts.google.com",
        "wa.me",
        "api.whatsapp.com",
        "snapchat.com",
        "pinterest.com",
        "reddit.com",
        "medium.com",
    }
)


@dataclass
class ExtractedSocial:
    platform: SocialPlatform
    profile_url: str
    username: str | None = None
    confidence_score: int = 70


@dataclass
class RichProfileData:
    """Rich social profile data extracted from profile pages."""

    followers: int | None = None
    following: int | None = None
    posts_count: int | None = None
    bio: str | None = None
    last_activity_at: str | None = None
    profile_image_url: str | None = None
    verified: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ── Social link extraction from HTML ──────────────────────────────────────────


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
            from urllib.parse import urljoin, urlparse

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


# ── Contact extraction ────────────────────────────────────────────────────────


def _extract_emails(html: str) -> dict[str, str]:
    """Extract best email from HTML. Returns {'public_email': email} or {}."""
    emails = [e for e in EMAIL_RE.findall(html) if is_valid_email(e)]
    # Prefer business emails
    for email in emails:
        if is_business_email(email):
            return {"public_email": email}
    if emails:
        return {"public_email": emails[0]}
    return {}


def _extract_phones(text: str) -> dict[str, str]:
    """Extract best phone from text. Returns {'public_phone': phone} or {}."""
    phones = PHONE_RE.findall(text)
    for p in phones:
        cleaned = p.strip()
        if len(cleaned) < 7:
            continue
        # Filter out date-like patterns (YYYYMMDD, YYYY-MM-DD, DD/MM/YYYY, etc.)
        digits_only = re.sub(r"[^\d]", "", cleaned)
        if re.match(r"^\d{4}[-/]?\d{2}[-/]?\d{2}$", cleaned.replace(" ", "")):
            continue
        # Filter out patterns like +20200505 (digits starting with 20 + 6 more = dates)
        if re.match(r"^\+?20\d{6}$", digits_only):
            continue
        # Filter out short codes that look like order/reference numbers
        if len(digits_only) <= 6:
            continue
        if not is_valid_phone_number(cleaned):
            continue
        try:
            phone = normalize_phone(cleaned)
            return {"public_phone": phone}
        except Exception:
            continue
    return {}


def _extract_website(html: str, profile_url: str, platform: str) -> dict[str, str]:
    """Extract business website link from profile page. Returns {'website': url} or {}."""
    from urllib.parse import urljoin, urlparse

    tree = HTMLParser(html)
    for a in tree.css("a[href]"):
        href = a.attrs.get("href", "")
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        try:
            full_href = urljoin(profile_url, href)
            parsed = urlparse(full_href)
            domain = parsed.netloc.removeprefix("www.").lower()
            if (
                domain
                and "." in domain
                and domain not in _SKIP_WEBSITE_DOMAINS
                and not any(d in domain for d in ["google.com", "fb.com"])
                and parsed.scheme in ("http", "https")
            ):
                link_text = (a.text() or "").strip().lower()
                if any(k in link_text for k in ["website", "site", "web", "business site"]):
                    return {"website": full_href}
                if platform == "LINKEDIN" and "website" not in {}:
                    return {"website": full_href}
        except Exception:
            continue
    return {}


# ── Rich profile data extraction (platform-specific) ──────────────────────────


def _parse_count(text: str) -> int | None:
    """Parse a human-readable count like '1.2K', '500K', '3M' into an integer."""
    if not text:
        return None
    text = text.strip().replace(",", "").replace(" ", "")
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    for suffix, mult in multipliers.items():
        if text.upper().endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return None
    try:
        return int(text)
    except ValueError:
        return None


def _extract_from_json_ld(html: str) -> dict[str, Any]:
    """Extract structured data from JSON-LD scripts."""
    tree = HTMLParser(html)
    for script in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text() or "")
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def _extract_meta_content(html: str, *names: str) -> str | None:
    """Extract content from meta tags by name or property."""
    tree = HTMLParser(html)
    for name in names:
        for sel in [f'meta[property="{name}"]', f'meta[name="{name}"]']:
            for meta in tree.css(sel):
                content = meta.attrs.get("content", "")
                if content:
                    return content
    return None


def _extract_facebook(html: str) -> RichProfileData:
    """Extract rich data from Facebook page HTML."""
    data = RichProfileData()
    # Likes/followers from og:description or meta
    desc = _extract_meta_content(html, "og:description", "description") or ""
    # "1.2K likes · 1.5K followers" pattern
    m = re.search(r"([\d.,]+[KMB]?)\s*likes?", desc, re.I)
    if m:
        data.followers = _parse_count(m.group(1))
    m = re.search(r"([\d.,]+[KMB]?)\s*followers?", desc, re.I)
    if m:
        data.followers = _parse_count(m.group(1))
    # Bio from og:description
    data.bio = desc[:500] if desc else None
    # Profile image
    data.profile_image_url = _extract_meta_content(html, "og:image")
    return data


def _extract_instagram(html: str) -> RichProfileData:
    """Extract rich data from Instagram profile HTML."""
    data = RichProfileData()
    # Instagram embeds data in meta tags and window._sharedData
    desc = _extract_meta_content(html, "og:description", "description") or ""
    # "X posts · Y followers · Z following" pattern
    m = re.search(r"([\d.,]+[KMB]?)\s*posts?", desc, re.I)
    if m:
        data.posts_count = _parse_count(m.group(1))
    m = re.search(r"([\d.,]+[KMB]?)\s*followers?", desc, re.I)
    if m:
        data.followers = _parse_count(m.group(1))
    m = re.search(r"([\d.,]+[KMB]?)\s*following", desc, re.I)
    if m:
        data.following = _parse_count(m.group(1))
    # Bio
    data.bio = desc[:500] if desc else None
    data.profile_image_url = _extract_meta_content(html, "og:image")
    return data


def _extract_linkedin(html: str) -> RichProfileData:
    """Extract rich data from LinkedIn company/person page."""
    data = RichProfileData()
    desc = _extract_meta_content(html, "og:description", "description") or ""
    # "X followers · Y employees" or "X followers on LinkedIn"
    m = re.search(r"([\d.,]+[KMB]?)\s*followers?", desc, re.I)
    if m:
        data.followers = _parse_count(m.group(1))
    # Employee count as proxy for company size
    m = re.search(r"([\d.,]+[KMB]?)\s*employees?", desc, re.I)
    if m:
        data.posts_count = _parse_count(m.group(1))
    data.bio = desc[:500] if desc else None
    data.profile_image_url = _extract_meta_content(html, "og:image")
    return data


def _extract_twitter(html: str) -> RichProfileData:
    """Extract rich data from Twitter/X profile."""
    data = RichProfileData()
    desc = _extract_meta_content(html, "og:description", "description") or ""
    # "X Followers · Y Following · Z Tweets"
    m = re.search(r"([\d.,]+[KMB]?)\s*[Ff]ollowers?", desc, re.I)
    if m:
        data.followers = _parse_count(m.group(1))
    m = re.search(r"([\d.,]+[KMB]?)\s*[Ff]ollowing", desc, re.I)
    if m:
        data.following = _parse_count(m.group(1))
    m = re.search(r"([\d.,]+[KMB]?)\s*[Tt]weets?", desc, re.I)
    if m:
        data.posts_count = _parse_count(m.group(1))
    data.bio = desc[:500] if desc else None
    data.profile_image_url = _extract_meta_content(html, "og:image")
    return data


def _extract_tiktok(html: str) -> RichProfileData:
    """Extract rich data from TikTok profile."""
    data = RichProfileData()
    desc = _extract_meta_content(html, "og:description", "description") or ""
    m = re.search(r"([\d.,]+[KMB]?)\s*[Ff]ollowers?", desc, re.I)
    if m:
        data.followers = _parse_count(m.group(1))
    m = re.search(r"([\d.,]+[KMB]?)\s*[Ll]ikes?", desc, re.I)
    if m:
        data.posts_count = _parse_count(m.group(1))
    data.bio = desc[:500] if desc else None
    data.profile_image_url = _extract_meta_content(html, "og:image")
    return data


def _extract_youtube(html: str) -> RichProfileData:
    """Extract rich data from YouTube channel."""
    data = RichProfileData()
    desc = _extract_meta_content(html, "og:description", "description") or ""
    m = re.search(r"([\d.,]+[KMB]?)\s*[Ss]ubscribers?", desc, re.I)
    if m:
        data.followers = _parse_count(m.group(1))
    m = re.search(r"([\d.,]+[KMB]?)\s*[Vv]ideos?", desc, re.I)
    if m:
        data.posts_count = _parse_count(m.group(1))
    data.bio = desc[:500] if desc else None
    data.profile_image_url = _extract_meta_content(html, "og:image")
    return data


_EXTRACTORS: dict[str, Callable] = {
    "FACEBOOK": _extract_facebook,
    "INSTAGRAM": _extract_instagram,
    "LINKEDIN": _extract_linkedin,
    "TWITTER": _extract_twitter,
    "TIKTOK": _extract_tiktok,
    "YOUTUBE": _extract_youtube,
}


def extract_rich_profile_data(html: str, platform: str) -> RichProfileData:
    """Extract rich profile data from HTML based on platform.

    Returns RichProfileData with whatever could be parsed.
    """
    extractor = _EXTRACTORS.get(platform)
    if extractor:
        try:
            return extractor(html)
        except Exception:
            pass
    # Fallback: generic extraction
    return RichProfileData()


# ── Combined scrape (contacts + rich data) ─────────────────────────────────────


async def scrape_social_profile_for_contacts(
    profile_url: str,
    platform: str,
    use_authenticated_session: bool = False,
    cdp_url: str = "http://localhost:9222",
) -> dict[str, Any]:
    """Scrape a social profile for public contact information."""
    result: dict[str, Any] = {}
    if not profile_url:
        return result

    log = logger.bind(platform=platform, url=profile_url)

    try:
        html: str | None = None
        if use_authenticated_session:
            try:
                from leadforge_scraper_core.browser_connector import (
                    fetch_with_authenticated_session,
                )

                html = await fetch_with_authenticated_session(profile_url, cdp_url=cdp_url)
            except Exception:
                pass

        if not html:
            from leadforge_scraper_core.base import fetch_html

            html = await fetch_html(
                profile_url, use_playwright=True, source="social_scraper", logger=log
            )

        if not html or len(html) < 200:
            log.debug("social_scrape.empty_or_blocked")
            return result

        result.update(_extract_emails(html))
        body = HTMLParser(html).body
        result.update(_extract_phones(body.text() if body else ""))
        result.update(_extract_website(html, profile_url, platform))

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


async def scrape_social_profile_rich(
    html: str,
    profile_url: str,
    platform: str,
) -> dict[str, Any]:
    """Scrape a social profile HTML for contacts + rich profile data.

    Args:
        html: Already-fetched HTML content.
        profile_url: Profile URL.
        platform: Platform name (FACEBOOK, INSTAGRAM, etc.).

    Returns:
        Dict with public_email, public_phone, website, followers,
        following, posts_count, bio, etc.
    """
    result: dict[str, Any] = {}
    if not html or len(html) < 200:
        return result

    try:
        # Contact info
        result.update(_extract_emails(html))
        tree = HTMLParser(html)
        text = tree.body.text() if tree.body else ""
        result.update(_extract_phones(text))
        result.update(_extract_website(html, profile_url, platform))

        # Rich profile data
        rich = extract_rich_profile_data(html, platform)
        # The platform extractors may not set last_activity_at — fall back to a
        # generic date sniff so the scoring engine has something to work with.
        if not rich.last_activity_at:
            rich.last_activity_at = _sniff_last_activity(html)
        result.update(rich.to_dict())

    except Exception as exc:
        logger.debug("scrape_rich.failed", url=profile_url, error=str(exc))

    return result


# ── Last-activity date sniffing ──────────────────────────────────────────────


_META_DATE_KEYS = (
    "og:updated_time",
    "article:modified_time",
    "article:published_time",
    "og:article:published_time",
    "og:article:modified_time",
    "lastmod",
    "pubdate",
    "date",
    "dc.date",
    "dc.date.modified",
    "dc.date.created",
)


def _sniff_last_activity(html: str) -> str | None:
    """Best-effort extraction of the profile's last-activity date string.

    Returns an ISO-8601 string suitable for storage, or ``None``.
    """
    if not html:
        return None

    # 1. Check standard meta tags first.
    for key in _META_DATE_KEYS:
        val = _extract_meta_content(html, key)
        if val and parse_iso_datetime(val) is not None:
            return val

    # 2. Fall back to relative phrases in body text.
    tree = HTMLParser(html)
    text = tree.body.text() if tree.body else ""
    parsed = parse_relative_phrase(text)
    return parsed.isoformat() if parsed else None
