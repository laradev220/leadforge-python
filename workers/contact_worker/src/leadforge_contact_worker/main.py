"""Contact worker. Mirrors workers/contact-worker/src/index.ts.

Enhanced to extract contacts from the existing business record (e.g. phone from
Google Maps) even when no website URL is available, rather than skipping entirely.
"""

import asyncio
import secrets
from uuid import UUID

from leadforge_database import get_session_ctx
from leadforge_database.models import Business, Contact, ContactSource, ContactType
from leadforge_database.provenance import record_provenance
from leadforge_scraper_core import crawl_website, extract_contacts, get_priority_urls
from leadforge_shared.types import ContactJobData
from leadforge_worker_core.core import WorkerWrapper, enqueue_job
from sqlalchemy import select


async def _extract_from_business_record(business_id, session, logger):
    """Extract contacts already stored on the Business record (e.g. phone from Google Maps).

    Google Maps often provides a phone number in the side panel data, which gets
    stored in ``businesses.phone`` during discovery. This function extracts that
    phone number into the ``contacts`` table so it's available for scoring.
    """
    result = await session.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        return

    phone = business.phone
    if not phone:
        return

    # Check if this phone is already in the contacts table
    existing = await session.execute(
        select(Contact).where(
            Contact.business_id == business_id,
            Contact.type == ContactType.PHONE,
            Contact.value == phone,
        )
    )
    if existing.scalar_one_or_none():
        return

    session.add(
        Contact(
            business_id=business_id,
            type=ContactType.PHONE,
            value=phone,
            source=ContactSource.MAPS,
            confidence_score=80,
            is_verified=False,
        )
    )
    await record_provenance(
        session,
        business_id=business_id,
        field="phone",
        value=phone,
        source="google_maps",
        confidence=80,
    )
    logger.info(
        "contact_extracted_from_business_record",
        businessId=str(business_id),
        type="PHONE",
        value=phone,
    )


async def contact_processor(data: ContactJobData, logger):
    business_id = data.business_id
    website_url = data.website_url
    logger.info("extracting_contacts", businessId=str(business_id), url=website_url)

    # If no website URL, still extract whatever contacts exist on the business record
    if not website_url:
        logger.warn("no_url_provided", businessId=str(business_id))
        async with get_session_ctx() as session:
            await _extract_from_business_record(business_id, session, logger)
            await session.commit()
        await enqueue_job("social", "social", {"business_id": str(business_id), "website_url": ""})
        return

    # Crawl homepage + priority pages with human-like delays between requests
    all_html = ""
    try:
        home_html = await crawl_website(website_url)
        all_html += home_html or ""

        priority_urls = get_priority_urls(website_url)
        for url in priority_urls:
            # Human-like delay between page fetches (pretend to read/click)
            await asyncio.sleep((1500 + secrets.randbelow(2001)) / 1000.0)
            page_html = await crawl_website(url)
            all_html += "\n" + (page_html or "")
    except Exception as e:
        logger.error("crawl_failed", businessId=str(business_id), error=str(e))

    async with get_session_ctx() as session:
        country = await session.scalar(select(Business.country).where(Business.id == business_id))
    region = country.upper() if country and len(country) == 2 else None
    contacts = await extract_contacts(all_html, website_url, region=region)
    logger.info("contacts_extracted", businessId=str(business_id), count=len(contacts))

    async with get_session_ctx() as session:
        # Also extract from business record (catches Google Maps phone data)
        await _extract_from_business_record(business_id, session, logger)

        for c in contacts:
            res = await session.execute(
                select(Contact).where(
                    Contact.business_id == business_id,
                    Contact.type == c.type,
                    Contact.value == c.value,
                )
            )
            if not res.scalar_one_or_none():
                session.add(
                    Contact(
                        business_id=business_id,
                        type=c.type,
                        value=c.value,
                        source="WEBSITE",
                        confidence_score=c.confidence_score,
                    )
                )
            await record_provenance(
                session,
                business_id=business_id,
                field=c.type.lower(),
                value=c.value,
                source="website",
                source_url=website_url,
                confidence=c.confidence_score,
            )
        await session.commit()

    await enqueue_job(
        "social", "social", {"business_id": str(business_id), "website_url": website_url}
    )


worker: WorkerWrapper[ContactJobData] = WorkerWrapper("contact", contact_processor)


# ── Module-level arq function ──────────────────────────────────────────────


async def contact(ctx: dict, business_id: str, website_url: str = "") -> None:
    """Arq entry point."""
    data = ContactJobData(business_id=UUID(business_id), website_url=website_url)
    await worker(ctx, data)


def main():
    """Entrypoint — arq 0.28's Worker.run() is synchronous."""
    from leadforge_worker_core.core import run_worker

    run_worker("contact", contact)


if __name__ == "__main__":
    main()
