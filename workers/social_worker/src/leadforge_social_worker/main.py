"""Social worker. Mirrors workers/social-worker/src/index.ts.

Enhanced to search for social profiles by business name when no website URL
is available, rather than skipping entirely.
"""

import asyncio
import re
from urllib.parse import quote_plus

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_config import get_settings
from leadforge_database import get_session_ctx
from leadforge_database.models import SocialProfile, Business
from leadforge_shared.types import SocialJobData
from leadforge_worker_core.core import WorkerWrapper, enqueue_job, get_arq_pool
from leadforge_scraper_core import crawl_website, extract_social_profiles, scrape_social_profile_for_contacts
from leadforge_scraper_core.social_platforms import (
    get_social_platform_search_terms,
    is_valid_phone_number,
)


async def _search_social_by_name(business_name: str) -> list[dict]:
    """Search for social profiles by business name using Google.

    Returns a list of dicts with keys: platform, profile_url, username.
    """
    profiles: list[dict] = []
    seen: set[str] = set()

    # Enhanced platform list including modern platforms
    # Use centralized social platform search terms
    search_terms = get_social_platform_search_terms()
    query = quote_plus(f"{business_name} {' OR '.join(search_terms)}")
    url = f"https://www.google.com/search?q={query}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    # Social platform domains mapping (centralized)
    SOCIAL_DOMAINS = {
        "facebook.com": "FACEBOOK",
        "fb.com": "FACEBOOK",
        "instagram.com": "INSTAGRAM",
        "linkedin.com": "LINKEDIN",
        "youtube.com": "YOUTUBE",
        "tiktok.com": "TIKTOK",
        "twitter.com": "TWITTER",
        "x.com": "TWITTER",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return profiles

            html = resp.text

            # Extract all hrefs from the page
            hrefs = re.findall(r'href="(https?://[^"]+?)"', html)
            for href in hrefs:
                if href in seen:
                    continue

                # Skip Google domains and non-social sites
                if any(d in href for d in ["google.com", "youtube.com", "accounts.google"]):
                    continue

                from urllib.parse import urlparse
                parsed = urlparse(href)
                domain = parsed.netloc.removeprefix("www.").lower()

                platform = SOCIAL_DOMAINS.get(domain)
                if not platform:
                    continue

                # Extract username from path
                path_parts = [p for p in parsed.path.split("/") if p and p not in ("in", "company")]
                username = path_parts[-1] if path_parts else None

                seen.add(href)
                profiles.append({
                    "platform": platform,
                    "profile_url": href,
                    "username": username,
                })
    except Exception:
        pass

    return profiles


async def social_processor(data: SocialJobData, logger):
    business_id = data.business_id
    website_url = data.website_url
    logger.info("discovering_social", businessId=str(business_id), url=website_url)

    profiles = []

    # If we have a website URL, crawl it for social links
    if website_url:
        try:
            html = await crawl_website(website_url)
            extracted = await extract_social_profiles(html or "", website_url)
            for ep in extracted:
                profiles.append({
                    "platform": ep.platform.value,
                    "profile_url": ep.profile_url,
                    "username": ep.username,
                })
        except Exception as e:
            logger.error("crawl_failed", businessId=str(business_id), error=str(e))
            # Continue with name-based search if website crawl fails

    # If we got nothing from the website, try name-based search
    if not profiles:
        logger.info("searching_social_by_name", businessId=str(business_id))

        # Get business name from the database with error handling
        try:
            async with get_session_ctx() as session:
                result = await session.execute(select(Business).where(Business.id == business_id))
                business = result.scalar_one_or_none()

            if business:
                name_profiles = await _search_social_by_name(business.name)
                profiles.extend(name_profiles)
                logger.info(
                    "social_profiles_found_by_name",
                    businessId=str(business_id),
                    count=len(name_profiles),
                )
            else:
                logger.warning("business_not_found", businessId=str(business_id))
        except Exception as e:
            logger.error("database_query_failed", businessId=str(business_id), error=str(e))
            # Continue without name-based search

    logger.info("profiles_extracted", businessId=str(business_id), count=len(profiles))

    async with get_session_ctx() as session:
        saved_profiles: list[SocialProfile] = []
        for p in profiles:
            try:
                # Check for existing profile by platform + url
                res = await session.execute(
                    select(SocialProfile).where(
                        SocialProfile.platform == p["platform"],
                        SocialProfile.profile_url == p["profile_url"]
                    )
                )
                existing = res.scalar_one_or_none()
                if existing:
                    existing.business_id = business_id
                    saved_profiles.append(existing)
                else:
                    sp = SocialProfile(
                        business_id=business_id,
                        platform=p["platform"],
                        profile_url=p["profile_url"],
                        username=p.get("username"),
                    )
                    session.add(sp)
                    saved_profiles.append(sp)
            except Exception as e:
                logger.error("profile_processing_failed", error=str(e), profile=p)
                continue
        await session.commit()

        # ── Scrape each found social profile for public contact info ──────────
    if saved_profiles:
        logger.info(
            "scraping_social_profiles_for_contacts",
            businessId=str(business_id),
            count=len(saved_profiles),
        )

        async def _scrape_and_update(sp: SocialProfile) -> dict:
            """Scrape a single profile and return update fields."""
            try:
                contacts = await scrape_social_profile_for_contacts(
                    sp.profile_url,
                    sp.platform.value,
                )
                return {"id": sp.id, **contacts} if contacts else {}
            except Exception as exc:
                logger.debug("social_profile_scrape_error", error=str(exc))
                return {}

        scrape_results = await asyncio.gather(
            *[_scrape_and_update(sp) for sp in saved_profiles],
            return_exceptions=True,
        )

        # Update records with found contact info
        async with get_session_ctx() as session:
            for result in scrape_results:
                if isinstance(result, Exception):
                    logger.debug("social_profile_scrape_error", error=str(result))
                    continue
                if not result or "id" not in result:
                    continue

                sp_id = result["id"]
                res = await session.execute(
                    select(SocialProfile).where(SocialProfile.id == sp_id)
                )
                sp = res.scalar_one_or_none()
                if not sp:
                    continue

                updated = False
                if result.get("public_email") and not sp.public_email:
                    sp.public_email = result["public_email"]
                    updated = True
                if result.get("public_phone") and not sp.public_phone:
                    sp.public_phone = result["public_phone"]
                    updated = True
                if result.get("website") and not sp.website:
                    sp.website = result["website"]
                    updated = True
                if updated:
                    logger.info(
                        "social_profile_contacts_updated",
                        businessId=str(business_id),
                        platform=sp.platform,
                        has_email=bool(sp.public_email),
                        has_phone=bool(sp.public_phone),
                        has_website=bool(sp.website),
                    )
            await session.commit()

    await enqueue_job("scoring", "scoring", {"business_id": str(business_id)})

worker = WorkerWrapper("social", social_processor)


# ── Module-level arq function ──────────────────────────────────────────────


async def social(ctx: dict, business_id: str, website_url: str = "") -> None:
    """Arq entry point."""
    data = SocialJobData(business_id=business_id, website_url=website_url)
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
                functions=[social],
                queue_name="social",
                redis_settings=RedisSettings(
                    host=settings.redis_host, port=settings.redis_port
                ),
                max_jobs=settings.scraper_concurrency,
            )
            worker_instance.run()
        except Exception as e:
            print(f"[social] worker crashed: {e}, restarting in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    main()
