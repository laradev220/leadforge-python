"""Verification worker.

Slice 1 is the tracer bullet: it marks email contacts UNKNOWN, records that the
stub ran, and hands off to scoring. Real MX/SMTP/provider checks land in Slice 2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from leadforge_database import get_session_ctx
from leadforge_database.models import Contact, ContactType
from leadforge_shared.types import VerificationJobData, VerificationStatus
from leadforge_worker_core.core import WorkerWrapper, enqueue_job
from sqlalchemy import select


async def verification_processor(data: VerificationJobData, log):
    business_id = data.business_id
    log.info("verifying_contacts", businessId=str(business_id), force=data.force)

    async with get_session_ctx() as session:
        result = await session.execute(select(Contact).where(Contact.business_id == business_id))
        contacts = list(result.scalars().all())

        updated = 0
        checked_at = datetime.now(UTC)
        for contact in contacts:
            if contact.type != ContactType.EMAIL:
                continue
            contact.verification_status = VerificationStatus.UNKNOWN
            contact.verification_confidence = 0
            contact.verification_reason = "not_implemented"
            contact.verification_method = "stub"
            contact.verified_at = checked_at
            contact.is_verified = False
            updated += 1

        await session.commit()

    log.info(
        "verification_completed",
        businessId=str(business_id),
        contacts=len(contacts),
        emails_updated=updated,
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
