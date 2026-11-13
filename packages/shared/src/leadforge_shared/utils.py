"""Pure utilities. Mirrors TS packages/shared/src/utils.ts."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import phonenumbers
from phonenumbers import NumberParseException

_PHONE_DIGITS_RE = re.compile(r"\D")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_phone(phone: str, region: str | None = None) -> str:
    """Best-effort E.164 normalization.

    ``region`` is an ISO-3166-1 alpha-2 code used to interpret national
    formats (e.g. UK ``020 7946 0958`` -> ``+442079460958``). Without it,
    only unambiguous formats are normalized; otherwise the raw digits are
    preserved instead of being mis-prefixed with a guessed country code.
    """
    raw = phone.strip()
    if not raw:
        return raw

    try:
        parsed = phonenumbers.parse(raw, region.upper() if region else None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except NumberParseException:
        pass

    digits = _PHONE_DIGITS_RE.sub("", raw)
    if not digits:
        return raw
    if raw.startswith("+"):
        return f"+{digits}"
    if raw.startswith("00") and len(digits) > 2:
        return f"+{digits[2:]}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        # Ambiguous: only assume NANP when no region was supplied.
        return f"+1{digits}" if region is None else f"+{digits}"
    # Do not silently drop a leading trunk zero or invent a country code.
    return raw


def extract_domain(url: str) -> str | None:
    try:
        host = urlparse(url).hostname or ""
    except (ValueError, TypeError):
        return None
    if not host:
        return None
    return host.removeprefix("www.")


def normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


def calculate_confidence(signals: list[dict[str, int | bool]]) -> int:
    total = sum(int(s["weight"]) for s in signals if s["present"])
    return min(total, 100)


def make_ext_id(source_slug: str, name: str) -> str:
    """Build a deterministic external ID in ``{source_slug}:{slug}`` format.

    The slug is derived from the business name: lowercase, non-alphanumeric
    characters replaced with underscores, leading/trailing underscores stripped.
    """
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return f"{source_slug}:{slug}"
