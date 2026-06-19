"""Pure utilities. Mirrors TS packages/shared/src/utils.ts."""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlparse

_PHONE_DIGITS_RE = re.compile(r"\D")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_phone(phone: str) -> str:
    digits = _PHONE_DIGITS_RE.sub("", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if digits.startswith("92") and len(digits) == 12:
        return f"+{digits}"
    if digits.startswith("0"):
        return f"+{digits[1:]}"
    return f"+{digits}"


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
