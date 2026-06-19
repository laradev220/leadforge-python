"""RegexStrategy — extracts emails, phones, and social handles via robust patterns.

This strategy is always applicable and runs after StructuredDataStrategy
(priority=20).  It augments results from earlier strategies rather than
producing standalone business records.
"""

from __future__ import annotations

import re
from typing import Any

from selectolax.parser import HTMLParser

from leadforge_scraper_core.strategies.base import (
    ExtractionStrategy,
    StrategyResult,
)


class RegexStrategy(ExtractionStrategy):
    """Extract contact-level data (emails, phones, social handles) via regex."""

    name = "regex"
    priority = 20

    def can_handle(self, html: str) -> bool:
        # Always applicable — regex is cheap
        return True

    async def extract(
        self,
        html: str,
        url: str,
        *,
        logger: Any = None,
    ) -> StrategyResult | None:
        tree = HTMLParser(html)
        text = tree.body.text() if tree.body else ""
        result = StrategyResult(strategy_name=self.name)

        emails = self._extract_emails(html)
        if emails:
            result.email = emails[0]
            result.extras["all_emails"] = emails

        phones = self._extract_phones(text)
        if phones:
            result.phone = phones[0]
            result.extras["all_phones"] = phones

        social = self._extract_social(html)
        if social:
            result.social_handles = social

        # Only return if we found something
        if result.email or result.phone or result.social_handles:
            result.confidence = 70
            return result
        return None

    # ── Email extraction ─────────────────────────────────────────────────────

    _EMAIL_RE = re.compile(
        r"""
        [a-zA-Z0-9._%+\\-]+   # local part
        @
        [a-zA-Z0-9.\\-]+       # domain
        \b
        """,
        re.VERBOSE,
    )

    # Patterns that are clearly not business contacts
    _DISCARD_EMAILS = {
        "noreply", "no-reply", "donotreply", "example", "test",
    }

    # Regex for phone: matches common formats including +1 (555) 123-4567
    _PHONE_RE = re.compile(
        r"""
        (?:\+?[1-9]\d{0,2}[\s.-]?)?   # optional country code
        \(?[2-9]\d{2}\)?               # area code with optional parens
        [\s.-]*\d{3}[\s.-]*\d{4}     # main number: 3 digits, space/dash, 4 digits
        """,
        re.VERBOSE,
    )

    def _extract_emails(self, html: str) -> list[str]:
        """Find all email addresses, discard generic/system ones."""
        found = self._EMAIL_RE.findall(html)
        seen = set()
        result = []
        for email in found:
            email_lower = email.lower()
            if email_lower in seen:
                continue
            local = email_lower.split("@")[0]
            if any(local.startswith(d) for d in self._DISCARD_EMAILS):
                continue
            # Skip freemail domains that are rarely business contacts
            domain = email_lower.split("@")[1]
            if domain in {
                "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                "icloud.com", "mail.com", "aol.com", "protonmail.com",
            }:
                continue
            seen.add(email_lower)
            result.append(email)
        return result[:10]  # cap at 10

    # ── Phone extraction ─────────────────────────────────────────────────────

    # Unified phone pattern for common formats
    _PHONE_RE = re.compile(
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

    def _extract_phones(self, text: str) -> list[str]:
        """Find phone numbers, normalise, deduplicate."""
        raw = self._PHONE_RE.findall(text)
        seen: set[str] = set()
        result = []
        for p in raw:
            # Strip punctuation, keep only digits and leading +
            digits = re.sub(r"[^\d+]", "", p)
            if digits.startswith("+"):
                digits = digits[1:]
            if len(digits) < 7 or len(digits) > 15:
                continue
            normalised = self._normalise_phone(digits)
            if normalised in seen:
                continue
            seen.add(normalised)
            result.append(p.strip())
        return result[:10]

    @staticmethod
    def _normalise_phone(digits: str) -> str:
        """Return a canonical digits-only string for dedup."""
        digits = re.sub(r"\b", "", digits)
        if digits.startswith("1") and len(digits) == 11:
            digits = digits[1:]
        return digits

    # ── Social handles extraction ────────────────────────────────────────────

    # Match social profile URLs in href attributes and text
    # Use single-backslash escapes in raw strings for regex metacharacters
    _SOCIAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r'facebook\.com/([a-zA-Z0-9._-]+)', re.I), "facebook"),
        (re.compile(r'(?:instagram\.com|instagr\.am)/([a-zA-Z0-9._-]+)', re.I), "instagram"),
        (re.compile(r'linkedin\.com/in/([a-zA-Z0-9._-]+)', re.I), "linkedin"),
        (re.compile(r'linkedin\.com/company/([a-zA-Z0-9._-]+)', re.I), "linkedin"),
        (re.compile(r'twitter\.com/([a-zA-Z0-9._-]+)', re.I), "twitter"),
        (re.compile(r'x\.com/([a-zA-Z0-9._-]+)', re.I), "twitter"),
        (re.compile(r'youtube\.com/@([a-zA-Z0-9._-]+)', re.I), "youtube"),
        (re.compile(r'youtube\.com/(?:channel/|c/)([a-zA-Z0-9._-]+)', re.I), "youtube"),
        (re.compile(r'tiktok\.com/@([a-zA-Z0-9._-]+)', re.I), "tiktok"),
    ]

    def _extract_social(self, html: str) -> dict[str, str]:
        """Find social profile URLs and map to platform names."""
        handles: dict[str, str] = {}
        seen: set[str] = set()
        for pattern, platform in self._SOCIAL_PATTERNS:
            for match in pattern.finditer(html):
                handle = match.group(1)
                if handle.lower() in seen:
                    continue
                seen.add(handle.lower())
                if platform not in handles:
                    handles[platform] = handle
        return handles