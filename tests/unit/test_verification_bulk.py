"""Bulk verification service and job-id dedupe."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from leadforge_api.services import verification_service
from leadforge_worker_core.core import verification_job_id


def _filters(**overrides):
    defaults = {
        "score_min": None,
        "score_max": None,
        "grade": None,
        "website_status": None,
        "best_contact_method": None,
        "city": None,
        "country": None,
        "verified_email": False,
        "has_mobile": False,
        "limit": 500,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


async def test_enqueue_bulk_uses_filters_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    ids = [uuid.uuid4(), uuid.uuid4()]
    captured: dict = {}
    enqueued: list[tuple] = []

    async def fake_find(_session, _user_id, **kwargs):
        captured.update(kwargs)
        return ids

    async def fake_enqueue(business_id, force=False):
        enqueued.append((business_id, force))

    monkeypatch.setattr(verification_service.lead_service, "find_lead_ids", fake_find)
    monkeypatch.setattr(verification_service, "enqueue_verification", fake_enqueue)

    queued = await verification_service.enqueue_bulk(
        None,
        uuid.uuid4(),
        filters=_filters(city="Peshawar", verified_email=True),
        force=True,
        limit=200,
    )

    assert queued == 2
    assert enqueued == [(ids[0], True), (ids[1], True)]
    assert captured["city"] == "Peshawar"
    assert captured["verified_email"] is True
    assert captured["limit"] == 200


async def test_enqueue_bulk_respects_schema_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    async def fake_find(_session, _user_id, **kwargs):
        captured.update(kwargs)
        return []

    async def fake_enqueue(*args, **kwargs):
        return None

    monkeypatch.setattr(verification_service.lead_service, "find_lead_ids", fake_find)
    monkeypatch.setattr(verification_service, "enqueue_verification", fake_enqueue)

    await verification_service.enqueue_bulk(
        None, uuid.uuid4(), filters=_filters(limit=50), limit=500
    )
    assert captured["limit"] == 50


def test_job_id_is_bucketed_by_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("leadforge_worker_core.core.time.time", lambda: 61.0)
    first = verification_job_id("biz-1")
    monkeypatch.setattr("leadforge_worker_core.core.time.time", lambda: 119.0)
    assert verification_job_id("biz-1") == first

    monkeypatch.setattr("leadforge_worker_core.core.time.time", lambda: 121.0)
    assert verification_job_id("biz-1") != first
