"""Discovery worker. Mirrors workers/discovery-worker/src/index.ts."""

from __future__ import annotations

from typing import Any

from leadforge_config import get_settings
from leadforge_database import get_session_ctx
from leadforge_database.models import (
    Business,
    SearchJob,
    SearchJobBusiness,
    SearchJobStatus,
    Website,
)
from leadforge_scraper_core import search_businesses
from leadforge_shared.types import DiscoveryJobData
from leadforge_shared.utils import extract_domain
from leadforge_worker_core.core import WorkerWrapper, enqueue_job
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


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

        job.status = SearchJobStatus.RUNNING
        await session.commit()

        # Search businesses — country is passed through to the source registry
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

        discovered_count = 0
        for biz in businesses:
            existing = await find_duplicate(session, biz)

            if existing:
                for key, value in biz.__dict__.items():
                    if key.startswith("_"):
                        continue
                    if key == "website":
                        continue  # relationship, not a column — handled below
                    if key == "phone":
                        value = _normalize_phone(value)
                    if value is not None and hasattr(existing, key):
                        setattr(existing, key, value)

                # Upsert Website record if Maps returned a URL
                website_url = getattr(biz, "website", None)
                if website_url:
                    res_web = await session.execute(
                        select(Website).where(Website.business_id == existing.id)
                    )
                    web_rec = res_web.scalar_one_or_none()
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
                    external_id=biz.external_id,
                    name=biz.name,
                    category=biz.category,
                    address=biz.address,
                    city=biz.city,
                    state=biz.state,
                    country=biz.country,
                    postal_code=biz.postal_code,
                    latitude=biz.latitude,
                    longitude=biz.longitude,
                    phone=_normalize_phone(biz.phone),
                    rating=biz.rating,
                    review_count=biz.review_count,
                    source=biz.source,
                )
                session.add(new_business)
                await session.flush()
                existing = new_business

                # Create Website record if Maps returned a URL
                website_url = getattr(biz, "website", None)
                if website_url:
                    session.add(
                        Website(
                            business_id=existing.id,
                            url=website_url,
                            domain=extract_domain(website_url),
                        )
                    )

            link = SearchJobBusiness(search_job_id=search_job_id, business_id=existing.id)
            session.add(link)
            discovered_count += 1

            # Enqueue website analysis (next pipeline stage)
            await enqueue_job("website", "website", {"business_id": str(existing.id)})

        job.status = SearchJobStatus.COMPLETED
        job.total_discovered = discovered_count
        await session.commit()
        logger.info(
            "discovery_completed",
            searchJobId=str(search_job_id),
            total=discovered_count,
        )


def _normalize_phone(phone: Any) -> str | None:
    """Normalize phone to a single string, handling lists.

    The scraper can return phone as a list of phone numbers or a single string.
    """
    if phone is None:
        return None
    if isinstance(phone, list):
        for p in phone:
            if p and isinstance(p, str) and p.strip():
                return p.strip()
        return None
    if isinstance(phone, str):
        return phone.strip() if phone.strip() else None
    return None


async def find_duplicate(session: AsyncSession, biz) -> Business | None:
    if biz.external_id:
        res = await session.execute(select(Business).where(Business.external_id == biz.external_id))
        if b := res.scalar_one_or_none():
            return b
    phone = _normalize_phone(getattr(biz, "phone", None))
    if phone:
        res = await session.execute(select(Business).where(Business.phone == phone))
        if b := res.scalar_one_or_none():
            return b
    return None


worker = WorkerWrapper("discovery", discovery_processor)


# ── Module-level arq function ──────────────────────────────────────────────
# arq v0.28 registers functions by ``__qualname__``.  Module-level functions
# naturally have ``__qualname__ == __name__``, so they always match the
# job name used in ``enqueue_job("discovery", ...)``.


async def discovery(ctx: dict, search_job_id: str, country: str | None = None) -> None:
    """Arq entry point — receives kwargs matching the enqueue payload."""
    data = DiscoveryJobData(search_job_id=search_job_id, country=country)
    await worker(ctx, data)


def main():
    """Entrypoint — arq 0.28's Worker.run() is synchronous."""
    import time

    from arq import Worker
    from arq.connections import RedisSettings

    settings = get_settings()
    while True:
        try:
            worker_instance = Worker(
                functions=[discovery],
                queue_name="discovery",
                redis_settings=RedisSettings(host=settings.redis_host, port=settings.redis_port, password=settings.redis_password or None),
                max_jobs=settings.scraper_concurrency,
            )
            worker_instance.run()
        except Exception as e:
            print(f"[discovery] worker crashed: {e}, restarting in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    main()
