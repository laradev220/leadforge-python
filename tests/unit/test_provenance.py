"""Provenance upserts and API mappings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from leadforge_api.schemas import ContactResponse, ProvenanceResponse
from leadforge_database.models import Contact, FieldProvenance
from leadforge_database.provenance import record_provenance
from leadforge_shared.types import (
    ContactSource,
    ContactType,
    PhoneLineType,
    VerificationStatus,
)


class _CapturingSession:
    def __init__(self) -> None:
        self.statements: list = []

    async def execute(self, statement):
        self.statements.append(statement)
        return SimpleNamespace()


async def test_record_provenance_upserts() -> None:
    session = _CapturingSession()
    business_id = uuid.uuid4()

    await record_provenance(
        session,
        business_id=business_id,
        field="email",
        value="info@clinic.pk",
        source="website",
        source_url="https://clinic.pk/contact",
        confidence=80,
    )

    assert len(session.statements) == 1
    sql = str(session.statements[0].compile())
    assert "ON CONFLICT" in sql
    assert "last_checked_at" in sql


async def test_record_provenance_skips_empty_values() -> None:
    session = _CapturingSession()
    business_id = uuid.uuid4()
    await record_provenance(
        session, business_id=business_id, field="email", value=None, source="website"
    )
    await record_provenance(
        session, business_id=business_id, field="email", value="   ", source="website"
    )
    assert session.statements == []


def test_contact_verification_payload() -> None:
    contact = Contact(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        type=ContactType.EMAIL,
        value="info@clinic.pk",
        source=ContactSource.WEBSITE,
        confidence_score=50,
        is_verified=True,
        verification_status=VerificationStatus.VALID,
        verification_confidence=94,
        verification_reason="smtp_250",
        verification_method="smtp",
        verified_at=datetime.now(UTC),
        line_type=None,
        created_at=datetime.now(UTC),
    )

    payload = contact.verification
    assert payload is not None
    assert payload["status"] == VerificationStatus.VALID
    assert payload["confidence"] == 94

    schema = ContactResponse.model_validate(contact)
    assert schema.verification is not None
    assert schema.verification.status == VerificationStatus.VALID


def test_unverified_contact_has_no_verification_payload() -> None:
    contact = Contact(
        business_id=uuid.uuid4(),
        type=ContactType.EMAIL,
        value="info@clinic.pk",
        verification_status=VerificationStatus.UNVERIFIED,
        verification_confidence=0,
        verified_at=None,
    )
    assert contact.verification is None


def test_provenance_response_maps_model() -> None:
    row = FieldProvenance(
        business_id=uuid.uuid4(),
        field="phone_type",
        value="+923329307688 (MOBILE)",
        source="verification",
        source_url=None,
        confidence=80,
        first_seen_at=datetime.now(UTC),
        last_checked_at=datetime.now(UTC),
    )
    payload = ProvenanceResponse.model_validate(row)
    assert payload.field == "phone_type"
    assert payload.confidence == 80


def test_phone_verification_payload_includes_line_type() -> None:
    contact = Contact(
        business_id=uuid.uuid4(),
        type=ContactType.PHONE,
        value="+923329307688",
        verification_status=VerificationStatus.VALID,
        verification_confidence=80,
        verified_at=datetime.now(UTC),
        line_type=PhoneLineType.MOBILE,
    )
    assert contact.verification is not None
    assert contact.verification["line_type"] == PhoneLineType.MOBILE
