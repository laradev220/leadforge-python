"""Website analysis. Mirrors packages/scraper-core/src/website.ts.

Improved to handle CDN/WAF 403 responses gracefully:
- httpx probe is tried first (fast, handles Cloudflare/hcdn 403 instantly)
- Playwright is then used for deeper JS analysis on reachable sites
- CDN 403 responses are marked reachable=True so downstream workers
  get the URL rather than giving up
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx
import structlog
from leadforge_shared.utils import extract_domain, normalize_url
from playwright.async_api import async_playwright

from leadforge_scraper_core.base import ACCEPT_ENCODING

logger = structlog.get_logger("scraper.website")


@dataclass
class WebsiteAnalysis:
    url: str
    domain: str | None
    ssl_enabled: bool
    is_reachable: bool
    http_status: int | None
    load_time_ms: int | None
    mobile_friendly: bool | None
    has_contact_form: bool
    seo_score: int


async def _httpx_probe(url: str) -> WebsiteAnalysis:
    """Fallback probe using httpx when Playwright fails.

    This handles sites that return non-blocking HTTP status codes (403, 401, etc.)
    where Playwright might throw or time out due to CDN/WAF blocking.
    """
    domain = extract_domain(url)
    ssl = url.startswith("https://")
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": ACCEPT_ENCODING,
                },
            )
            load_time = int((time.time() - start) * 1000)
            # 403 means the site IS reachable but blocking automated requests.
            # Explicit 403 check makes the intent clear even though 403 < 500.
            reachable = resp.status_code < 500 or resp.status_code == 403
            return WebsiteAnalysis(
                url=url,
                domain=domain,
                ssl_enabled=ssl,
                is_reachable=reachable,
                http_status=resp.status_code,
                load_time_ms=load_time,
                mobile_friendly=None,
                has_contact_form=False,
                seo_score=0,
            )
    except Exception:
        load_time = int((time.time() - start) * 1000)
        return WebsiteAnalysis(
            url=url,
            domain=domain,
            ssl_enabled=False,
            is_reachable=False,
            http_status=None,
            load_time_ms=load_time,
            mobile_friendly=None,
            has_contact_form=False,
            seo_score=0,
        )


async def _playwright_analyze(url: str) -> WebsiteAnalysis | None:
    """Try full Playwright analysis. Returns None if it fails entirely."""
    domain = extract_domain(url)
    ssl = url.startswith("https://")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = await context.new_page()

            start = time.time()
            response = await page.goto(url, wait_until="domcontentloaded", timeout=5000)
            load_time = int((time.time() - start) * 1000)

            status = response.status if response else None
            reachable = status is not None and (status < 500 or status == 403)

            if not reachable:
                await browser.close()
                return None

            viewport_el = await page.query_selector('meta[name="viewport"]')
            mobile = True if viewport_el else None

            forms = await page.query_selector_all("form")
            has_form = False
            for f in forms:
                html = await f.inner_html()
                if any(k in html.lower() for k in ["email", "message", "contact"]):
                    has_form = True
                    break

            seo = 50
            title = await page.title()
            if title and len(title) > 10:
                seo += 15
            desc = await page.get_attribute('meta[name="description"]', "content")
            if desc and len(desc) > 50:
                seo += 15
            h1 = await page.query_selector("h1")
            if h1:
                seo += 10
            if ssl:
                seo += 10

            await browser.close()
            return WebsiteAnalysis(
                url=url,
                domain=domain,
                ssl_enabled=ssl,
                is_reachable=reachable,
                http_status=status,
                load_time_ms=load_time,
                mobile_friendly=mobile,
                has_contact_form=has_form,
                seo_score=min(seo, 100),
            )
    except Exception as exc:
        logger.debug("playwright_analysis_failed", url=url, error=str(exc))
        return None


async def analyze_website(raw_url: str) -> WebsiteAnalysis:
    """Analyze a website with httpx probe first, then Playwright enrichment.

    Approach:
    1. Try httpx first (fast, handles CDN/WAF 403 instantly)
    2. If httpx reports reachable, try Playwright for deeper JS analysis
       (extracts viewport, contact forms, SEO metadata)
    3. If Playwright fails, return httpx result (site is still reachable)
    4. If httpx fails, mark as unreachable

    This order ensures CDN-blocked sites (like those behind Cloudflare's
    hcdn returning 403) are correctly marked reachable without waiting
    for Playwright's slow timeout/cleanup cycle.
    """
    url = normalize_url(raw_url)

    # Stage 1: Fast httpx probe
    probe = await _httpx_probe(url)

    if not probe.is_reachable:
        # Site is truly unreachable (DNS failure, connection timeout, etc.)
        return probe

    # Stage 2: Try Playwright for deeper analysis (viewport, forms, SEO)
    # Run with a short timeout to avoid blocking the pipeline
    try:
        rich = await asyncio.wait_for(
            _playwright_analyze(url),
            timeout=12.0,
        )
        if rich is not None:
            return rich
    except TimeoutError:
        logger.debug("playwright_analysis_timed_out", url=url)
    except Exception as exc:
        logger.debug("playwright_analysis_error", url=url, error=str(exc))

    # Stage 3: Playwright enrichment failed; return httpx probe result
    return probe
