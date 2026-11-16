"""Recurring schedule math, validation, and scheduler tick."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from leadforge_api.schemas import ScheduleCreateRequest
from leadforge_scheduler_worker import main as scheduler
from leadforge_shared.scheduling import compute_next_run
from leadforge_shared.types import ScheduleCadence
from pydantic import ValidationError

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


class TestNextRun:
    def test_daily_same_day_if_future(self) -> None:
        result = compute_next_run(now=NOW, cadence=ScheduleCadence.DAILY, hour=15, minute=30)
        assert result == datetime(2026, 11, 16, 15, 30, tzinfo=UTC)

    def test_daily_rolls_to_tomorrow(self) -> None:
        result = compute_next_run(now=NOW, cadence=ScheduleCadence.DAILY, hour=9, minute=0)
        assert result == datetime(2026, 11, 17, 9, 0, tzinfo=UTC)

    def test_weekly_next_weekday(self) -> None:
        # 2026-11-16 is a Monday; next Wednesday 08:00.
        result = compute_next_run(
            now=NOW, cadence=ScheduleCadence.WEEKLY, weekday=2, hour=8, minute=0
        )
        assert result == datetime(2026, 11, 18, 8, 0, tzinfo=UTC)

    def test_weekly_same_weekday_already_passed(self) -> None:
        result = compute_next_run(
            now=NOW, cadence=ScheduleCadence.WEEKLY, weekday=0, hour=8, minute=0
        )
        assert result == datetime(2026, 11, 23, 8, 0, tzinfo=UTC)

    def test_monthly_next_month(self) -> None:
        result = compute_next_run(
            now=NOW, cadence=ScheduleCadence.MONTHLY, day_of_month=10, hour=9, minute=0
        )
        assert result == datetime(2026, 12, 10, 9, 0, tzinfo=UTC)

    def test_timezone_conversion(self) -> None:
        # 09:00 in Karachi is 04:00 UTC.
        result = compute_next_run(
            now=NOW,
            cadence=ScheduleCadence.DAILY,
            hour=9,
            minute=0,
            tz_name="Asia/Karachi",
        )
        assert result == datetime(2026, 11, 17, 4, 0, tzinfo=UTC)

    def test_unknown_timezone_falls_back_to_utc(self) -> None:
        result = compute_next_run(
            now=NOW,
            cadence=ScheduleCadence.DAILY,
            hour=15,
            minute=0,
            tz_name="Not/AZone",
        )
        assert result.tzinfo == UTC


class TestScheduleSchema:
    def test_weekly_requires_weekday(self) -> None:
        with pytest.raises(ValidationError):
            ScheduleCreateRequest(
                keyword="Dentist",
                location="Peshawar",
                cadence="WEEKLY",
                hour=9,
                minute=0,
            )

    def test_valid_weekly(self) -> None:
        body = ScheduleCreateRequest(
            keyword="Dentist",
            location="Peshawar",
            cadence="WEEKLY",
            weekday=1,
            hour=9,
            minute=0,
            timezone="Asia/Karachi",
        )
        assert body.weekday == 1

    def test_unknown_timezone_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ScheduleCreateRequest(
                keyword="Dentist",
                location="Peshawar",
                cadence="DAILY",
                timezone="Not/AZone",
            )


class TestSchedulerTick:
    async def test_due_schedule_creates_job_and_advances(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        schedule = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            keyword="Dentist",
            location="Peshawar",
            country="PK",
            radius_km=10,
            cadence=ScheduleCadence.DAILY,
            hour=9,
            minute=0,
            weekday=None,
            day_of_month=None,
            timezone="UTC",
            enabled=True,
            next_run_at=datetime(2026, 11, 16, 8, 0, tzinfo=UTC),
            last_run_at=None,
            last_job_id=None,
        )
        added: list = []
        enqueued: list = []

        class _Result:
            def scalars(self):
                return self

            def all(self):
                return [schedule]

        class _Session:
            async def execute(self, _stmt):
                return _Result()

            def add(self, obj):
                obj.id = uuid.uuid4()
                added.append(obj)

            async def flush(self):
                return None

            async def commit(self):
                return None

        @asynccontextmanager
        async def fake_ctx():
            yield _Session()

        async def fake_enqueue(queue_name, job_name, payload):
            enqueued.append((queue_name, job_name, payload))

        monkeypatch.setattr(scheduler, "get_session_ctx", fake_ctx)
        monkeypatch.setattr(scheduler, "enqueue_job", fake_enqueue)

        dispatched = await scheduler.tick_once()

        assert dispatched == 1
        assert len(added) == 1
        assert schedule.last_job_id == added[0].id
        assert schedule.next_run_at > schedule.last_run_at
        assert enqueued[0][0:2] == ("discovery", "discovery")
        assert enqueued[0][2]["country"] == "PK"
