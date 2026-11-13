"""Relative/absolute date parsing shared by scrapers and workers.

Kept in one place so the scraper-side sniffer and the worker-side parser
cannot drift apart.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

# "3 days ago", "an hour ago", "a month ago"
RELATIVE_RE = re.compile(
    r"(\d+|a|an)\s+(second|minute|hour|day|week|month|year)s?\s+ago",
    re.IGNORECASE,
)

_RELATIVE_UNITS: dict[str, timedelta] = {
    "second": timedelta(seconds=1),
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}


def parse_iso_datetime(value: str) -> datetime | None:
    """Parse an ISO-8601 string into a tz-aware datetime (UTC when naive)."""
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def parse_relative_phrase(value: str, *, now: datetime | None = None) -> datetime | None:
    """Convert ``"3 days ago"`` into an absolute datetime. None when not a relative phrase."""
    match = RELATIVE_RE.search(value)
    if not match:
        return None
    raw_count, unit = match.group(1).lower(), match.group(2).lower()
    try:
        count = 1 if raw_count in ("a", "an") else int(raw_count)
    except ValueError:
        return None
    base = now or datetime.now(UTC)
    return base - _RELATIVE_UNITS[unit] * count


def parse_last_activity(value: str | None, *, now: datetime | None = None) -> datetime | None:
    """Parse either an ISO-8601 timestamp or a relative phrase. None on failure."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    return parse_iso_datetime(text) or parse_relative_phrase(text, now=now)
