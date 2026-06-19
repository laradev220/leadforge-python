"""Website worker with website discovery fallback.

If a business has no known website, the worker attempts to find one via
search engine (Google) before marking it as NOT_FOUND.
"""

from __future__ import annotations

from urllib.parse import quote_plus

import httpx
from leadforge_config import get_settings
from leadforge_database import get_session_ctx
from leadforge_database.models import Business, Website, WebsiteStatus
from leadforge_scraper_core import analyze_website
from leadforge_shared.types import WebsiteJobData
from leadforge_worker_core.core import WorkerWrapper, enqueue_job
from sqlalchemy import select


async def _discover_website(business_name: str, location: str | None = None) -> str | None:
    """Attempt to find a business website via Google search.

    Uses a simple Google search with a 10-second timeout.
    """
    query = business_name
    if location:
        query += f" {location}"
    query += " official website"

    url = f"https://www.google.com/search?q={quote_plus(query)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None

            html = resp.text

            # Parse organic results — look for the first .g .kCrYT or similar
            import re

            # Match Google result URLs (various formats)
            patterns = [
                r'href="(https?://(?:www\.)?'
                + re.escape(business_name.lower().split()[0])
                + r'[^"]*?)"',
                r'<a[^>]*href="(https?://[^"]+?)"[^>]*><[^>]*><h3[^>]*>',
                r'<a[^>]*href="(/url\?q=https?://[^&"]+)[^"]*"',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, html, re.I)
                for m in matches[:5]:
                    decoded = m.replace("/url?q=", "").split("&")[0] if "/url?q=" in m else m
                    if (
                        decoded.startswith("http")
                        and "google.com" not in decoded
                        and "youtube.com" not in decoded
                        and "facebook.com" not in decoded
                        and "instagram.com" not in decoded
                        and "linkedin.com" not in decoded
                    ):
                        return decoded.split("?")[0]

            # Broader pattern: any link containing the business name
            name_slug = quote_plus(business_name.lower())
            broad = re.findall(
                r'href="(https?://[^"]+?' + re.escape(name_slug.split("%20")[0]) + r'[^"]+?)"',
                html,
                re.I,
            )
            for m in broad[:3]:
                if m.startswith("http") and "google.com" not in m and "youtube.com" not in m:
                    return m.split("?")[0]

    except Exception as exc:
        import structlog

        log = structlog.get_logger("website_worker.discovery")
        log.warning("website_discovery_failed", business=business_name, error=str(exc))
        return None

    return None


async def website_processor(data: WebsiteJobData, logger):
    business_id = data.business_id
    logger.info("processing_website", businessId=str(business_id))

    async with get_session_ctx() as session:
        result = await session.execute(select(Business).where(Business.id == business_id))
        business = result.scalar_one_or_none()
        if not business:
            logger.error("business_not_found", businessId=str(business_id))
            raise ValueError("Business not found")

        # Extract business fields into locals immediately to avoid
        # potential lazy-loading / MissingGreenlet issues when accessed
        # inside nested async calls (e.g. _discover_website with httpx).
        business_name = business.name
        business_city = business.city
        business_state = business.state

        # Determine URL — from existing website record or from business.website
        website_url = ""
        res_web = await session.execute(select(Website).where(Website.business_id == business_id))
        website = res_web.scalar_one_or_none()

        if website:
            website_url = website.url
        else:
            # No website known — attempt discovery via search engine
            logger.info(
                "attempting_website_discovery",
                businessId=str(business_id),
                name=business_name,
            )
            discovered_url = await _discover_website(business_name, business_city or business_state)
            if discovered_url:
                logger.info(
                    "website_discovered",
                    businessId=str(business_id),
                    url=discovered_url,
                )
                website = Website(
                    business_id=business_id,
                    url=discovered_url,
                )
                session.add(website)
                await session.flush()
                website_url = discovered_url
            else:
                logger.info(
                    "website_not_found",
                    businessId=str(business_id),
                    name=business.name,
                )
                business.website_status = WebsiteStatus.NOT_FOUND
                await session.commit()
                await enqueue_job(
                    "contact", "contact", {"business_id": str(business_id), "website_url": ""}
                )
                return

        # Analyze the website
        analysis = await analyze_website(website_url)

        if website:
            website.ssl_enabled = analysis.ssl_enabled
            website.is_reachable = analysis.is_reachable
            website.http_status = analysis.http_status
            website.load_time_ms = analysis.load_time_ms
            website.mobile_friendly = analysis.mobile_friendly
            website.seo_score = analysis.seo_score

        business.website_status = (
            WebsiteStatus.FOUND if analysis.is_reachable else WebsiteStatus.INVALID
        )

        await session.commit()
        logger.info(
            "website_analyzed",
            businessId=str(business_id),
            status=business.website_status.value,
            reachable=analysis.is_reachable,
        )

        website_url_to_pass = analysis.url if analysis.is_reachable else ""
        await enqueue_job(
            "contact",
            "contact",
            {
                "business_id": str(business_id),
                "website_url": website_url_to_pass,
            },
        )


worker = WorkerWrapper("website", website_processor)


# ── Module-level arq function ──────────────────────────────────────────────


async def website(ctx: dict, business_id: str) -> None:
    """Arq entry point."""
    data = WebsiteJobData(business_id=business_id)
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
                functions=[website],
                queue_name="website",
                redis_settings=RedisSettings(host=settings.redis_host, port=settings.redis_port),
                max_jobs=settings.scraper_concurrency,
            )
            worker_instance.run()
        except Exception as e:
            print(f"[website] worker crashed: {e}, restarting in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    main()
