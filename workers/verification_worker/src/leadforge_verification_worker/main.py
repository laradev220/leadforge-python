"""Verification worker.

Slice 2: real domain-level (MX) email checks and offline phone line typing.
SMTP/provider mailbox checks arrive in a later slice.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from leadforge_database import get_session_ctx
from leadforge_database.models import Business, Contact, ContactType
from leadforge_shared.types import (
    PhoneLineType,
    VerificationJobData,
    VerificationStatus,
)
from leadforge_verification import (
    EmailVerifier,
    build_email_verifier,
    classify_phone,
    verify_email,
)
from leadforge_worker_core.core import WorkerWrapper, enqueue_job
from sqlalchemy import select

_verifier: EmailVerifier | None = None


def _get_verifier() -> EmailVerifier:
    global _verifier
    if _verifier is None:
        _verifier = build_email_verifier()
    return _verifier


def _apply(
    contact: Contact,
    *,
    status: VerificationStatus,
    confidence: int,
    reason: str | None,
    method: str,
) -> None:
    contact.verification_status = status
    contact.verification_confidence = confidence
    contact.verification_reason = reason
    contact.verification_method = method
    contact.verified_at = datetime.now(UTC)
    contact.is_verified = status == VerificationStatus.VALID


async def verification_processor(data: VerificationJobData, log):
    business_id = data.business_id
    log.info("verifying_contacts", businessId=str(business_id), force=data.force)

    verifier = _get_verifier()

    async with get_session_ctx() as session:
        country = await session.scalar(select(Business.country).where(Business.id == business_id))
        region = country.upper() if country and len(country) == 2 else None

        result = await session.execute(select(Contact).where(Contact.business_id == business_id))
        contacts = list(result.scalars().all())

        emails = 0
        phones = 0
        for contact in contacts:
            if contact.type == ContactType.EMAIL:
                outcome = await verify_email(contact.value, verifier)
                _apply(
                    contact,
                    status=outcome.status,
                    confidence=outcome.confidence,
                    reason=outcome.reason,
                    method=outcome.method,
                )
                emails += 1
            elif contact.type == ContactType.PHONE:
                line_type, normalized = classify_phone(contact.value, region)
                if normalized is None:
                    _apply(
                        contact,
                        status=VerificationStatus.UNKNOWN,
                        confidence=0,
                        reason="unparseable_phone",
                        method="phone_lib",
                    )
                else:
                    contact.value = normalized
                    contact.line_type = line_type
                    _apply(
                        contact,
                        status=VerificationStatus.VALID,
                        confidence=80 if line_type != PhoneLineType.UNKNOWN else 40,
                        reason=f"line_type:{line_type.value.lower()}",
                        method="phone_lib",
                    )
                phones += 1

        await session.commit()

    log.info(
        "verification_completed",
        businessId=str(business_id),
        contacts=len(contacts),
        emails=emails,
        phones=phones,
    )
    await enqueue_job("scoring", "scoring", {"business_id": str(business_id)})


worker: WorkerWrapper[VerificationJobData] = WorkerWrapper("verification", verification_processor)


async def verification(ctx: dict, business_id: str, force: bool = False) -> None:
    """Arq entry point."""
    data = VerificationJobData(business_id=UUID(business_id), force=force)
    await worker(ctx, data)


def main():
    """Entrypoint — arq 0.28's Worker.run() is synchronous."""
    from leadforge_worker_core.core import run_worker

    run_worker("verification", verification)


if __name__ == "__main__":
    main()
