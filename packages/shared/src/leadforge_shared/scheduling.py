"""Next-run math for recurring searches."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from leadforge_shared.types import ScheduleCadence


def _zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def compute_next_run(
    *,
    now: datetime,
    cadence: ScheduleCadence | str,
    hour: int,
    minute: int,
    weekday: int | None = None,
    day_of_month: int | None = None,
    tz_name: str = "UTC",
) -> datetime:
    """Next UTC instant that matches the cadence after ``now``."""
    zone = _zone(tz_name)
    local_now = now.astimezone(zone)
    cadence = ScheduleCadence(cadence)

    def candidate(day: datetime) -> datetime:
        return day.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if cadence == ScheduleCadence.DAILY:
        next_local = candidate(local_now)
        if next_local <= local_now:
            next_local = candidate(local_now + timedelta(days=1))
    elif cadence == ScheduleCadence.WEEKLY:
        target = 0 if weekday is None else max(0, min(6, weekday))
        days_ahead = (target - local_now.weekday()) % 7
        next_local = candidate(local_now + timedelta(days=days_ahead))
        if next_local <= local_now:
            next_local = candidate(local_now + timedelta(days=days_ahead + 7))
    else:
        day = max(1, min(28, day_of_month or 1))
        year, month = local_now.year, local_now.month
        day = max(day, 1)
        day = min(day, calendar.monthrange(year, month)[1])
        next_local = candidate(local_now.replace(day=day))
        if next_local <= local_now:
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
            day = min(day, calendar.monthrange(year, month)[1])
            next_local = candidate(local_now.replace(year=year, month=month, day=day))

    return next_local.astimezone(UTC).replace(tzinfo=UTC)
