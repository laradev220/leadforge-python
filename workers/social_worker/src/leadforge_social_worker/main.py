"""Social worker — discovers and scrapes social profiles for businesses.

Uses Chrome CDP authenticated session for:
  - Google searches (bypasses bot detection)
  - Social profile scraping (low ban rate)

Rate-limits profile scrapes sequentially with configurable delays.
"""

import asyncio
import re
import secrets
from urllib.parse import quote_plus, urlparse

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_config import get_settings
from leadforge_database import get_session_ctx
from leadforge_database.models import SocialProfile, Business
from leadforge_shared.types import SocialJobData
from leadforge_worker_core.core import WorkerWrapper, enqueue_job
from leadforge_scraper_core import extract_social_profiles, scrape_social_profile_rich
from leadforge_scraper_core.social_platforms import get_social_platform_search_terms

logger = structlog.get_logger("worker.social")

# ── Social domain mapping for Google result parsing ───────────────────────────
_SOCIAL_DOMAINS = {
    "facebook.com": "FACEBOOK",
    "fb.com": "FACEBOOK",
    "instagram.com": "INSTAGRAM",
    "linkedin.com": "LINKEDIN",
    "youtube.com": "YOUTUBE",
    "tiktok.com": "TIKTOK",
    "twitter.com": "TWITTER",
    "x.com": "TWITTER",
}


# ── Google search: httpx fallback ─────────────────────────────────────────────

async def _search_social_by_name_httpx(business_name: str) -> list[dict]:
    """Search Google for social profiles using plain HTTP."""
    profiles: list[dict] = []
    seen: set[str] = set()
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

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return profiles

            hrefs = re.findall(r'href="(https?://[^"]+?)"', resp.text)
            for href in hrefs:
                if href in seen:
                    continue
                if any(d in href for d in ["google.com", "accounts.google"]):
                    continue

                parsed = urlparse(href)
                domain = parsed.netloc.removeprefix("www.").lower()
                platform = _SOCIAL_DOMAINS.get(domain)
                if not platform:
                    continue

                path_parts = [p for p in parsed.path.split("/") if p and p not in ("in", "company")]
                username = path_parts[-1] if path_parts else None
                seen.add(href)
                profiles.append({"platform": platform, "profile_url": href, "username": username})
    except Exception:
        pass

    return profiles


# ── Google search: CDP-based ──────────────────────────────────────────────────

async def _search_social_by_name_cdp(
    business_name: str,
    cdp_url: str,
) -> list[dict]:
    """Search Google for social profiles using authenticated Chrome session."""
    from leadforge_scraper_core.browser_connector import CDPBrowser

    profiles: list[dict] = []
    seen: set[str] = set()
    search_terms = get_social_platform_search_terms()
    query = quote_plus(f"{business_name} {' OR '.join(search_terms)}")
    url = f"https://www.google.com/search?q={query}"

    browser = None
    try:
        browser = await CDPBrowser.create(cdp_url=cdp_url)
        async with browser.tab_context(url) as tab:
            await asyncio.sleep(2 + secrets.randbelow(3))
            html = await tab.get_html()

        if not html or len(html) < 200:
            return profiles

        hrefs = re.findall(r'href="(https?://[^"]+?)"', html)
        for href in hrefs:
            if href in seen:
                continue
            if any(d in href for d in ["google.com", "accounts.google"]):
                continue

            parsed = urlparse(href)
            domain = parsed.netloc.removeprefix("www.").lower()
            platform = _SOCIAL_DOMAINS.get(domain)
            if not platform:
                continue

            path_parts = [p for p in parsed.path.split("/") if p and p not in ("in", "company")]
            username = path_parts[-1] if path_parts else None
            seen.add(href)
            profiles.append({"platform": platform, "profile_url": href, "username": username})
    except Exception as exc:
        logger.debug("cdp_google_search.failed", error=str(exc))
    finally:
        if browser:
            try:
                await browser.disconnect()
            except Exception:
                pass

    return profiles


async def _search_social_by_name(
    business_name: str,
    use_cdp: bool = True,
    cdp_url: str = "http://localhost:9222",
) -> list[dict]:
    """Search for social profiles by business name.

    Tries CDP first, falls back to httpx.
    """
    if use_cdp:
        profiles = await _search_social_by_name_cdp(business_name, cdp_url)
        if profiles:
            return profiles
    return await _search_social_by_name_httpx(business_name)


# ── Main processor ────────────────────────────────────────────────────────────

async def social_processor(data: SocialJobData, log):
    business_id = data.business_id
    website_url = data.website_url
    settings = get_settings()

    cdp_url = settings.chrome_cdp_url
    use_cdp = settings.use_authenticated_session
    scrape_delay_ms = settings.social_scrape_delay_ms

    log.info("discovering_social", businessId=str(business_id), url=website_url, cdp_enabled=use_cdp)

    profiles = []

    # ── Phase 1: Discover social profiles ─────────────────────────────────
    if website_url:
        try:
            from leadforge_scraper_core import crawl_website
            html = await crawl_website(website_url)
            extracted = await extract_social_profiles(html or "", website_url)
            for ep in extracted:
                profiles.append({
                    "platform": ep.platform.value,
                    "profile_url": ep.profile_url,
                    "username": ep.username,
                })
        except Exception as e:
            log.error("crawl_failed", businessId=str(business_id), error=str(e))

    if not profiles:
        log.info("searching_social_by_name", businessId=str(business_id))
        try:
            async with get_session_ctx() as session:
                result = await session.execute(select(Business).where(Business.id == business_id))
                business = result.scalar_one_or_none()

            if business:
                name_profiles = await _search_social_by_name(
                    business.name, use_cdp=use_cdp, cdp_url=cdp_url,
                )
                profiles.extend(name_profiles)
                log.info("social_profiles_found_by_name", businessId=str(business_id), count=len(name_profiles))
            else:
                log.warning("business_not_found", businessId=str(business_id))
        except Exception as e:
            log.error("database_query_failed", businessId=str(business_id), error=str(e))

    log.info("profiles_extracted", businessId=str(business_id), count=len(profiles))

    # ── Phase 1.5: Deduplicate profiles by normalized URL ──────────────────
    def _normalize_url(url: str) -> str:
        return url.rstrip("/").lower()

    seen_normalized: dict[str, dict] = {}
    for p in profiles:
        key = f"{p['platform']}:{_normalize_url(p['profile_url'])}"
        if key not in seen_normalized:
            seen_normalized[key] = p
    profiles = list(seen_normalized.values())

    # ── Phase 2: Save profiles to DB ──────────────────────────────────────
    async with get_session_ctx() as session:
        saved_profiles: list[SocialProfile] = []
        for p in profiles:
            normalized_url = _normalize_url(p["profile_url"])
            try:
                # Check by normalized URL (strip trailing slash)
                res = await session.execute(
                    select(SocialProfile).where(
                        SocialProfile.platform == p["platform"],
                    )
                )
                existing = None
                for sp in res.scalars():
                    if _normalize_url(sp.profile_url) == normalized_url:
                        existing = sp
                        break
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
                log.error("profile_processing_failed", error=str(e), profile=p)
                continue
        await session.commit()

    # ── Phase 3: Scrape profiles (rate-limited, sequential) ───────────────
    if not saved_profiles:
        await enqueue_job("scoring", "scoring", {"business_id": str(business_id)})
        return

    log.info(
        "scraping_social_profiles",
        businessId=str(business_id),
        count=len(saved_profiles),
        delay_ms=scrape_delay_ms,
    )

    # Open one CDPBrowser for all scrapes
    browser = None
    if use_cdp:
        try:
            from leadforge_scraper_core.browser_connector import CDPBrowser
            browser = await CDPBrowser.create(cdp_url=cdp_url)
        except Exception as exc:
            log.warning("cdp_browser_unavailable", error=str(exc))
            use_cdp = False

    try:
        for idx, sp in enumerate(saved_profiles, 1):
            log.info(
                "scraping_profile",
                businessId=str(business_id),
                platform=sp.platform,
                profile=idx,
                total=len(saved_profiles),
                url=sp.profile_url,
            )

            try:
                contacts = await _scrape_profile(sp, browser=browser, cdp_url=cdp_url, use_cdp=use_cdp)
                if contacts:
                    await _update_profile(sp, contacts, session=None)
            except Exception as exc:
                log.debug("profile_scrape_error", platform=sp.platform, error=str(exc))

            # Rate limit between scrapes (not after the last one)
            if idx < len(saved_profiles):
                delay = scrape_delay_ms + secrets.randbelow(max(1, scrape_delay_ms // 3)) - scrape_delay_ms // 6
                actual_ms = max(1000, delay)
                log.debug("scrape_delay", ms=actual_ms)
                await asyncio.sleep(actual_ms / 1000.0)
    finally:
        if browser:
            await browser.disconnect()

    # ── Phase 4: Batch update DB ──────────────────────────────────────────
    async with get_session_ctx() as session:
        for sp in saved_profiles:
            try:
                res = await session.execute(select(SocialProfile).where(SocialProfile.id == sp.id))
                db_sp = res.scalar_one_or_none()
                if db_sp and hasattr(sp, '_contacts'):
                    contacts = sp._contacts
                    updated = False
                    for field_name in ("public_email", "public_phone", "website"):
                        val = contacts.get(field_name)
                        if val and not getattr(db_sp, field_name):
                            setattr(db_sp, field_name, val)
                            updated = True
                    for field_name in ("followers", "following", "posts_count", "bio", "profile_image_url"):
                        val = contacts.get(field_name)
                        if val and not getattr(db_sp, field_name):
                            setattr(db_sp, field_name, val)
                            updated = True
                    if updated:
                        log.info("profile_updated", platform=db_sp.platform, fields=list(contacts.keys()))
            except Exception as e:
                log.error("profile_update_failed", error=str(e))
        await session.commit()

    await enqueue_job("scoring", "scoring", {"business_id": str(business_id)})


async def _scrape_profile(
    sp: SocialProfile,
    browser=None,
    cdp_url: str = "http://localhost:9222",
    use_cdp: bool = True,
) -> dict:
    """Scrape a single profile for contacts + rich data."""
    if use_cdp and browser:
        from leadforge_scraper_core.browser_connector import CDPBrowser
        async with browser.tab_context(sp.profile_url) as tab:
            await asyncio.sleep(1.5 + secrets.randbelow(3))
            html = await tab.get_html()
        if html and len(html) > 200:
            return await scrape_social_profile_rich(html, sp.profile_url, sp.platform.value)
        return {}

    # Fallback: httpx/Playwright — fetch HTML then use rich scraper
    from leadforge_scraper_core.base import fetch_html
    from leadforge_scraper_core.social import scrape_social_profile_rich

    log = logger.bind(platform=sp.platform, url=sp.profile_url)
    try:
        html = await fetch_html(sp.profile_url, use_playwright=True, source="social_scraper", logger=log)
        if html and len(html) > 200:
            return await scrape_social_profile_rich(html, sp.profile_url, sp.platform.value)
    except Exception as exc:
        log.debug("httpx_scrape.failed", error=str(exc))
    return {}


async def _update_profile(sp: SocialProfile, contacts: dict, session=None) -> None:
    """Store contacts on the profile object for later batch DB update."""
    sp._contacts = contacts  # type: ignore[attr-defined]


# ── Arq entry point ───────────────────────────────────────────────────────────

worker = WorkerWrapper("social", social_processor)


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
