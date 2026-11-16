"""Discovery worker. Mirrors workers/discovery-worker/src/index.ts."""

from __future__ import annotations

import re
import uuid
from typing import Any
from uuid import UUID

from leadforge_database import get_session_ctx
from leadforge_database.models import (
    Business,
    SearchJob,
    SearchJobBusiness,
    SearchJobStatus,
    Website,
)
from leadforge_database.provenance import record_many
from leadforge_scraper_core import search_businesses
from leadforge_shared.types import DiscoveryJobData
from leadforge_shared.utils import extract_domain, normalize_phone
from leadforge_worker_core.core import WorkerWrapper, enqueue_job
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

_CANCEL_CHECK_EVERY = 5


def _slug(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _same_business(existing: Business, biz: Any) -> bool:
    """Guard against merging distinct businesses that share a name/slug."""
    if existing.name.strip().lower() != biz.name.strip().lower():
        return False
    if existing.city and biz.city:
        return existing.city.strip().lower() == biz.city.strip().lower()
    return True


async def _unique_external_id(session: AsyncSession, biz: Any) -> str | None:
    """Return an external ID that does not collide with a different business."""
    base = biz.external_id
    if not base:
        return None
    taken = await session.scalar(select(Business.id).where(Business.external_id == base))
    if taken is None:
        return base

    suffix = _slug(getattr(biz, "city", None) or getattr(biz, "country", None))
    if suffix:
        candidate = f"{base}:{suffix}"
        taken = await session.scalar(select(Business.id).where(Business.external_id == candidate))
        if taken is None:
            return candidate
    return f"{base}:{uuid.uuid4().hex[:8]}"


async def _mark_job_failed(session: AsyncSession, search_job_id: uuid.UUID) -> None:
    try:
        await session.rollback()
        job = (
            await session.execute(select(SearchJob).where(SearchJob.id == search_job_id))
        ).scalar_one_or_none()
        if job is not None:
            job.status = SearchJobStatus.FAILED
            await session.commit()
    except Exception:
        await session.rollback()


async def discovery_processor(data: DiscoveryJobData, logger):
    search_job_id = data.search_job_id
    country = data.country
    logger.info(
        "processing_discovery",
        searchJobId=str(search_job_id),
        country=country,
    )

    async with get_session_ctx() as session:
        result = await session.execute(select(SearchJob).where(SearchJob.id == search_job_id))
        job = result.scalar_one_or_none()
        if not job:
            logger.error("search_job_not_found", searchJobId=str(search_job_id))
            raise ValueError(f"Search job {search_job_id} not found")

        if job.status == SearchJobStatus.CANCELLED:
            logger.info("search_job_cancelled", searchJobId=str(search_job_id))
            return

        job.status = SearchJobStatus.RUNNING
        await session.commit()

        try:
            businesses = await search_businesses(
                keyword=job.keyword,
                location=job.location,
                country=country,
            )
            logger.info(
                "businesses_discovered",
                searchJobId=str(search_job_id),
                count=len(businesses),
            )

            # Google Maps/directory rows frequently omit city/country; the
            # searched location is the best available fallback.
            location_city = (job.location or "").split(",")[0].strip() or None
            location_country = country.upper() if country else None

            discovered_count = 0
            to_enqueue: list[uuid.UUID] = []

            for index, biz in enumerate(businesses):
                if index and index % _CANCEL_CHECK_EVERY == 0:
                    await session.refresh(job, ["status"])
                    if job.status == SearchJobStatus.CANCELLED:
                        logger.info("search_job_cancelled", searchJobId=str(search_job_id))
                        return

                phone_region = country or getattr(biz, "country", None)
                existing = await find_duplicate(session, biz)

                if existing:
                    for key, value in biz.__dict__.items():
                        if key.startswith("_"):
                            continue
                        if key == "website":
                            continue  # relationship, not a column — handled below
                        if key == "phone":
                            value = _normalize_phone(value, phone_region)
                        if value is not None and hasattr(existing, key):
                            setattr(existing, key, value)
                    if not existing.city and location_city:
                        existing.city = location_city

                    website_url = getattr(biz, "website", None)
                    if website_url:
                        web_rec = (
                            await session.execute(
                                select(Website).where(Website.business_id == existing.id)
                            )
                        ).scalar_one_or_none()
                        if web_rec:
                            web_rec.url = website_url
                            web_rec.domain = extract_domain(website_url)
                        else:
                            session.add(
                                Website(
                                    business_id=existing.id,
                                    url=website_url,
                                    domain=extract_domain(website_url),
                                )
                            )
                else:
                    new_business = Business(
                        external_id=await _unique_external_id(session, biz),
                        name=biz.name,
                        category=biz.category,
                        address=biz.address,
                        city=biz.city or location_city,
                        state=biz.state,
                        country=biz.country or location_country,
                        postal_code=biz.postal_code,
                        latitude=biz.latitude,
                        longitude=biz.longitude,
                        phone=_normalize_phone(biz.phone, phone_region),
                        rating=biz.rating,
                        review_count=biz.review_count,
                        source=biz.source,
                    )
                    session.add(new_business)
                    await session.flush()
                    existing = new_business

                    website_url = getattr(biz, "website", None)
                    if website_url:
                        session.add(
                            Website(
                                business_id=existing.id,
                                url=website_url,
                                domain=extract_domain(website_url),
                            )
                        )

                await record_many(
                    session,
                    business_id=existing.id,
                    values={
                        "name": biz.name,
                        "category": biz.category,
                        "address": biz.address,
                        "city": biz.city or location_city,
                        "country": biz.country or location_country,
                        "phone": _normalize_phone(biz.phone, phone_region),
                        "website": getattr(biz, "website", None),
                        "rating": biz.rating,
                    },
                    source=(biz.source or "discovery").lower(),
                    source_url=getattr(biz, "website", None),
                    confidence=80,
                )

                link_exists = await session.scalar(
                    select(SearchJobBusiness.id).where(
                        SearchJobBusiness.search_job_id == search_job_id,
                        SearchJobBusiness.business_id == existing.id,
                    )
                )
                if link_exists is None:
                    session.add(
                        SearchJobBusiness(search_job_id=search_job_id, business_id=existing.id)
                    )
                    to_enqueue.append(existing.id)

                discovered_count += 1

            job.status = SearchJobStatus.COMPLETED
            job.total_discovered = discovered_count
            await session.commit()
        except Exception:
            await _mark_job_failed(session, search_job_id)
            raise

        # Enqueue only after the transaction commits: queued jobs must never
        # reference rows that were rolled back.
        for business_id in to_enqueue:
            await enqueue_job("website", "website", {"business_id": str(business_id)})

        logger.info(
            "discovery_completed",
            searchJobId=str(search_job_id),
            total=discovered_count,
            queued=len(to_enqueue),
        )


def _normalize_phone(phone: Any, region: str | None = None) -> str | None:
    """Normalize phone to a single string, handling lists."""
    if phone is None:
        return None
    if isinstance(phone, list):
        for candidate in phone:
            if candidate and isinstance(candidate, str) and candidate.strip():
                phone = candidate
                break
        else:
            return None
    if not isinstance(phone, str):
        return None
    cleaned = phone.strip()
    if not cleaned:
        return None
    iso_region = region if region and len(region) == 2 else None
    return normalize_phone(cleaned, iso_region)


async def find_duplicate(session: AsyncSession, biz) -> Business | None:
    if biz.external_id:
        res = await session.execute(select(Business).where(Business.external_id == biz.external_id))
        if b := res.scalar_one_or_none():
            # Same slug but a different location/name is a distinct business.
            if _same_business(b, biz):
                return b

    phone = _normalize_phone(getattr(biz, "phone", None))
    if phone:
        res = await session.execute(
            select(Business).where(
                Business.phone == phone,
                func.lower(Business.name) == biz.name.strip().lower(),
            )
        )
        if b := res.scalar_one_or_none():
            return b
    return None


worker: WorkerWrapper[DiscoveryJobData] = WorkerWrapper("discovery", discovery_processor)


# ── Module-level arq function ──────────────────────────────────────────────


async def discovery(ctx: dict, search_job_id: str, country: str | None = None) -> None:
    """Arq entry point — receives kwargs matching the enqueue payload."""
    data = DiscoveryJobData(search_job_id=UUID(search_job_id), country=country)
    await worker(ctx, data)


def main():
    """Entrypoint — arq 0.28's Worker.run() is synchronous."""
    from leadforge_worker_core.core import run_worker

    run_worker("discovery", discovery)


if __name__ == "__main__":
    main()
