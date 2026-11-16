"""Verification worker tests (Slice 2: MX + phone typing)."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from leadforge_database.models import ContactType
from leadforge_shared.types import (
    PhoneLineType,
    VerificationJobData,
    VerificationStatus,
)
from leadforge_verification.types import VerificationResult
from leadforge_verification_worker import main as worker_main


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, contacts, country="PK"):
        self.contacts = contacts
        self.country = country
        self.committed = False

    async def scalar(self, _statement):
        return self.country

    async def execute(self, _statement):
        return _FakeResult(self.contacts)

    async def commit(self):
        self.committed = True


class _FakeVerifier:
    def __init__(self, status=VerificationStatus.RISKY):
        self.status = status
        self.calls: list[str] = []

    async def verify(self, value: str) -> VerificationResult:
        self.calls.append(value)
        return VerificationResult(
            status=self.status,
            confidence=60,
            reason="mx_present",
            method="mx",
            checked_at=datetime.now(UTC),
        )


def _contact(
    contact_type: ContactType, value: str, *, verified_at: datetime | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        type=contact_type,
        value=value,
        verification_status=VerificationStatus.UNVERIFIED,
        verification_confidence=50,
        verification_reason=None,
        verification_method=None,
        verified_at=verified_at,
        line_type=None,
        is_verified=False,
    )


def test_job_payload_defaults() -> None:
    business_id = uuid.uuid4()
    data = VerificationJobData.model_validate({"business_id": str(business_id)})
    assert data.business_id == business_id
    assert data.force is False


async def test_worker_verifies_email_and_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    business_id = uuid.uuid4()
    email = _contact(ContactType.EMAIL, "contact@dentalsquarefamily.com")
    phone = _contact(ContactType.PHONE, "0332 9307688")
    session = _FakeSession([email, phone])
    enqueued: list[tuple] = []
    verifier = _FakeVerifier()

    @asynccontextmanager
    async def fake_ctx():
        yield session

    async def fake_enqueue(queue_name, job_name, payload, **kwargs):
        enqueued.append((queue_name, job_name, payload))

    monkeypatch.setattr(worker_main, "get_session_ctx", fake_ctx)
    monkeypatch.setattr(worker_main, "enqueue_job", fake_enqueue)
    monkeypatch.setattr(worker_main, "_get_verifier", lambda: verifier)

    await worker_main.verification_processor(
        VerificationJobData(business_id=business_id), SimpleNamespace(info=lambda *a, **k: None)
    )

    assert session.committed
    assert email.verification_status == VerificationStatus.RISKY
    assert email.verification_method == "mx"
    assert email.is_verified is False

    assert phone.verification_status == VerificationStatus.VALID
    assert phone.line_type == PhoneLineType.MOBILE
    assert phone.value == "+923329307688"
    assert phone.is_verified is True

    assert verifier.calls == ["contact@dentalsquarefamily.com"]
    assert enqueued == [("scoring", "scoring", {"business_id": str(business_id)})]


async def test_worker_handles_unparseable_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    business_id = uuid.uuid4()
    phone = _contact(ContactType.PHONE, "not-a-phone")
    session = _FakeSession([phone])

    @asynccontextmanager
    async def fake_ctx():
        yield session

    async def fake_enqueue(*args, **kwargs):
        return None

    monkeypatch.setattr(worker_main, "get_session_ctx", fake_ctx)
    monkeypatch.setattr(worker_main, "enqueue_job", fake_enqueue)
    fake_verifier = _FakeVerifier()
    monkeypatch.setattr(worker_main, "_get_verifier", lambda: fake_verifier)

    await worker_main.verification_processor(
        VerificationJobData(business_id=business_id), SimpleNamespace(info=lambda *a, **k: None)
    )

    assert phone.verification_status == VerificationStatus.UNKNOWN
    assert phone.verification_reason == "unparseable_phone"
    assert phone.line_type is None


async def test_worker_skips_fresh_contacts(monkeypatch: pytest.MonkeyPatch) -> None:
    business_id = uuid.uuid4()
    email = _contact(ContactType.EMAIL, "info@clinic.pk", verified_at=datetime.now(UTC))
    phone = _contact(
        ContactType.PHONE, "+923329307688", verified_at=datetime.now(UTC) - timedelta(days=3)
    )
    session = _FakeSession([email, phone])
    verifier = _FakeVerifier()
    enqueued: list[tuple] = []

    @asynccontextmanager
    async def fake_ctx():
        yield session

    async def fake_enqueue(queue_name, job_name, payload, **kwargs):
        enqueued.append((queue_name, job_name, payload))

    monkeypatch.setattr(worker_main, "get_session_ctx", fake_ctx)
    monkeypatch.setattr(worker_main, "enqueue_job", fake_enqueue)
    monkeypatch.setattr(worker_main, "_get_verifier", lambda: verifier)

    await worker_main.verification_processor(
        VerificationJobData(business_id=business_id), SimpleNamespace(info=lambda *a, **k: None)
    )

    assert verifier.calls == []
    assert email.verification_status == VerificationStatus.UNVERIFIED
    assert enqueued[0][0] == "scoring"


async def test_worker_force_reverifies(monkeypatch: pytest.MonkeyPatch) -> None:
    business_id = uuid.uuid4()
    email = _contact(ContactType.EMAIL, "info@clinic.pk", verified_at=datetime.now(UTC))
    session = _FakeSession([email])
    verifier = _FakeVerifier()

    @asynccontextmanager
    async def fake_ctx():
        yield session

    async def fake_enqueue(*args, **kwargs):
        return None

    monkeypatch.setattr(worker_main, "get_session_ctx", fake_ctx)
    monkeypatch.setattr(worker_main, "enqueue_job", fake_enqueue)
    monkeypatch.setattr(worker_main, "_get_verifier", lambda: verifier)

    await worker_main.verification_processor(
        VerificationJobData(business_id=business_id, force=True),
        SimpleNamespace(info=lambda *a, **k: None),
    )

    assert verifier.calls == ["info@clinic.pk"]
    assert email.verification_status == VerificationStatus.RISKY
