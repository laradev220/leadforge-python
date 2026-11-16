"""Slice 1: verification worker tracer bullet."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from leadforge_database.models import ContactType
from leadforge_shared.types import VerificationJobData, VerificationStatus
from leadforge_verification_worker import main as worker_main


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, contacts):
        self.contacts = contacts
        self.committed = False

    async def execute(self, _statement):
        return _FakeResult(self.contacts)

    async def commit(self):
        self.committed = True


def _contact(contact_type: ContactType) -> SimpleNamespace:
    return SimpleNamespace(
        type=contact_type,
        verification_status=VerificationStatus.UNVERIFIED,
        verification_confidence=50,
        verification_reason=None,
        verification_method=None,
        verified_at=None,
        is_verified=False,
    )


def test_job_payload_defaults() -> None:
    business_id = uuid.uuid4()
    data = VerificationJobData.model_validate({"business_id": str(business_id)})
    assert data.business_id == business_id
    assert data.force is False


async def test_stub_marks_emails_unknown_and_enqueues_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    business_id = uuid.uuid4()
    email = _contact(ContactType.EMAIL)
    phone = _contact(ContactType.PHONE)
    session = _FakeSession([email, phone])
    enqueued: list[tuple] = []

    @asynccontextmanager
    async def fake_ctx():
        yield session

    async def fake_enqueue(queue_name, job_name, payload, **kwargs):
        enqueued.append((queue_name, job_name, payload))

    monkeypatch.setattr(worker_main, "get_session_ctx", fake_ctx)
    monkeypatch.setattr(worker_main, "enqueue_job", fake_enqueue)

    log = SimpleNamespace(info=lambda *a, **k: None)
    await worker_main.verification_processor(VerificationJobData(business_id=business_id), log)

    assert session.committed
    assert email.verification_status == VerificationStatus.UNKNOWN
    assert email.verification_method == "stub"
    assert email.verified_at is not None
    assert phone.verification_status == VerificationStatus.UNVERIFIED
    assert enqueued == [("scoring", "scoring", {"business_id": str(business_id)})]


async def test_worker_with_no_contacts_still_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    business_id = uuid.uuid4()
    session = _FakeSession([])
    enqueued: list[tuple] = []

    @asynccontextmanager
    async def fake_ctx():
        yield session

    async def fake_enqueue(queue_name, job_name, payload, **kwargs):
        enqueued.append((queue_name, job_name, payload))

    monkeypatch.setattr(worker_main, "get_session_ctx", fake_ctx)
    monkeypatch.setattr(worker_main, "enqueue_job", fake_enqueue)

    await worker_main.verification_processor(
        VerificationJobData(business_id=business_id), SimpleNamespace(info=lambda *a, **k: None)
    )

    assert enqueued[0][0] == "scoring"
