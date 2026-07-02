"""Refactored Google Maps scraper — no-proxy / human-like mode.

Key improvements for no-proxy operation:
  - Human-like mouse movement and scrolling via human_simulation.py
  - Selective resource blocking only (allows images/CSS to load for realism)
  - Randomised timing and viewport per session
  - Reduced scroll speed with natural acceleration/deceleration
  - Variable delays between clicks and scrolls (500–3000ms)
  - Opportunistic extraction from window.APP_INITIAL_STATE
  - Circuit breaker per source
  - All extraction strategies composed

Designed to handle 5–10 requests/hour without proxies.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import structlog
from leadforge_config import get_settings
from playwright.async_api import Page, ViewportSize, async_playwright
from tenacity import after_log, retry, stop_after_attempt, wait_exponential_jitter

from leadforge_scraper_core import metrics as scraper_metrics
from leadforge_scraper_core.exceptions import CircuitOpenError
from leadforge_scraper_core.human_simulation import (
    human_delay,
    human_scroll,
    jitter,
)
from leadforge_scraper_core.monitors.circuit_breaker import get_circuit_breaker

logger = structlog.get_logger("scraper.google_maps")


@dataclass
class MapsBusiness:
    external_id: str
    name: str
    category: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    review_count: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    source: str = "GOOGLE_MAPS"


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
]

_VIEWPORTS: list[ViewportSize] = [
    ViewportSize(width=1920, height=1080),
    ViewportSize(width=1440, height=900),
    ViewportSize(width=1366, height=768),
    ViewportSize(width=1536, height=864),
    ViewportSize(width=1280, height=720),
]

_BOT_SIGNALS = [
    "unusual traffic",
    "captcha",
    "cf-browser-verification",
    "sorry",
    "automated queries",
    "blocked",
]

_PLACEHOLDER_NAMES: frozenset[str] = frozenset(
    {
        "Google Maps",
        "Google",
        "Maps",
        "Map",
        "Google Maps Platform",
    }
)

# Domains of known third-party/aggregator platforms that commonly appear in
# Google Maps side panel data but are NOT the business's own website.
# These are services like online ordering, reservations, review aggregators, etc.
_PLATFORM_DOMAINS: frozenset[str] = frozenset(
    {
        # Online ordering / reservations
        "opentable.com",
        "opentable.co.uk",
        "opentable.ca",
        "sevenrooms.com",
        "resy.com",
        "tockhq.com",
        "bookatable.com",
        "eatout.co.uk",
        "toptable.com",
        "squareup.com",
        "order.store",
        "orderswift.com",
        "orderlord.com",
        # Delivery platforms
        "just-eat.com",
        "just-eat.co.uk",
        "deliveroo.com",
        "deliveroo.co.uk",
        "ubereats.com",
        "doordash.com",
        "grubhub.com",
        "postmates.com",
        # Review / directory aggregators
        "tripadvisor.com",
        "tripadvisor.co.uk",
        "yelp.com",
        "yelp.co.uk",
        "foursquare.com",
        "thefork.com",
        "thefork.co.uk",
        "zomato.com",
        # Social / booking (not the business's own site)
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "tiktok.com",
        "youtube.com",
        "twitter.com",
        "x.com",
        # Vague business service domains (often wrong)
        "bizify.co.uk",
        "bizify.com",
        "citylocalpro.com",
        "hotfrog.com",
        "hotfrog.co.uk",
        "cylex.co.uk",
        "cylex.com",
    }
)


def _normalize_phone(phone: Any) -> str | None:
    """Normalize phone to a single string, handling lists or other types.

    Google Maps internal state can return phone as a list of numbers,
    a single string, or None. This ensures we always pass a string or None.
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
    return str(phone) if phone else None


def _is_placeholder_name(name: str) -> bool:
    """Return True if *name* is a known placeholder (e.g. page title) not a real business name."""
    return name.strip() in _PLACEHOLDER_NAMES or len(name.strip()) < 3


def _is_platform_url(url: str | None) -> bool:
    """Return True if *url* is a known third-party/aggregator platform, not a business's own website.

    Google Maps side panel often shows reservation/ordering platforms like
    opentable.co.uk or sevenrooms.com instead of the business's own site.
    We reject these so the website worker can discover the real site.
    """
    if not url:
        return False
    try:
        hostname = urllib.parse.urlparse(url).hostname or ""
        hostname = hostname.removeprefix("www.").lower()
        for domain in _PLATFORM_DOMAINS:
            if hostname == domain or hostname.endswith("." + domain):
                return True
    except Exception:
        pass
    return False


def _check_for_block(html: str | None = None) -> bool:
    if html is None:
        return False
    lower = html.lower()
    return any(signal in lower for signal in _BOT_SIGNALS)


async def _collect_place_urls(page: Page, max_scrolls: int = 8) -> list[dict[str, Any]]:
    """Scroll the results feed and collect place URLs with feed metadata.

    Returns a list of dicts with keys: url, name, rating, review_count,
    address, category.  Metadata is extracted from ARIA labels and feed
    item text on the search results page.
    """
    await human_delay(2000, 4000, page=page)

    seen_urls: set[str] = set()
    results: list[dict[str, Any]] = []

    for scroll_num in range(max_scrolls):
        current_count = len(seen_urls)

        # Human-like scroll — variable distance, multiple small wheel ticks
        scroll_dist = random.randint(400, 900)
        scroll_steps = random.randint(4, 8)
        try:
            feed = await page.query_selector('[role="feed"]')
            if feed:
                for _ in range(scroll_steps):
                    step_dist = scroll_dist // scroll_steps
                    await feed.evaluate(f"el => el.scrollBy(0, {step_dist})")
                    await asyncio.sleep(jitter(80, 60))
            else:
                await human_scroll(page, scroll_dist, max_steps=scroll_steps)
        except Exception:
            with contextlib.suppress(Exception):
                await page.evaluate(f"window.scrollBy(0, {scroll_dist})")

        # Wait for new results to load
        await human_delay(2000, 5000, page=page)

        # Collect fresh place URLs + metadata from feed items
        try:
            feed_items = await _extract_feed_items(page)
            for item in feed_items:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    results.append(item)
        except Exception:
            pass

        # If no new results after a scroll, feed is likely exhausted
        new_count = len(seen_urls)
        if scroll_num > 0 and new_count <= current_count + 1:
            logger.debug("google_maps.feed_exhausted", scroll_num=scroll_num)
            break

    return results[:20]


async def _extract_feed_items(page: Page) -> list[dict[str, Any]]:
    """Extract business data from feed items on the search results page.

    Uses ARIA labels and inner text — the most reliable way to get
    ratings, review counts, and addresses from Google Maps.
    """
    raw = await page.evaluate("""
        () => {
            const feed = document.querySelector('[role="feed"]');
            if (!feed) return [];
            const items = feed.querySelectorAll('[role="article"]');
            return Array.from(items).map(item => {
                const text = item.innerText || '';
                const ariaLabels = Array.from(item.querySelectorAll('[aria-label]'))
                    .map(e => e.getAttribute('aria-label'))
                    .filter(l => l);
                // Find the place link URL
                const link = item.querySelector('a[href*="/maps/place/"]');
                const url = link ? link.getAttribute('href') : '';
                return { text, ariaLabels, url };
            });
        }
    """)
    if not raw:
        return []

    results: list[dict[str, Any]] = []
    for item in raw:
        url = item.get("url", "")
        if not url:
            continue
        if url.startswith("/"):
            url = f"https://www.google.com{url}"

        text = item.get("text", "")
        aria_labels = item.get("ariaLabels", [])

        # Extract name from aria-label (first non-generic label)
        name = None
        for label in aria_labels:
            if (
                label
                and "star" not in label.lower()
                and "review" not in label.lower()
                and "sponsored" not in label.lower()
                and "accessible" not in label.lower()
                and "price" not in label.lower()
                and len(label) > 2
            ):
                name = label
                break

        # Extract rating and review count from aria-label
        # Formats: "4.7 stars 3,901 Reviews", "4.7 stars, 3,901 reviews",
        #          "4.7 stars", "4.5 (3,901)", "Rated 4.7 out of 5"
        rating = None
        review_count = None
        for label in aria_labels:
            # Try full: "4.7 stars 3,901 Reviews"
            m = re.search(
                r"(\d+\.?\d*)\s*stars?[\s,]*([\d,]+)\s*reviews?",
                label,
                re.I,
            )
            if m:
                try:
                    rating = float(m.group(1))
                    review_count = int(m.group(2).replace(",", ""))
                except (ValueError, TypeError):
                    pass
                break
            # Try just stars: "4.5 stars"
            m = re.search(r"(\d+\.?\d*)\s*stars?$", label, re.I)
            if m:
                with contextlib.suppress(ValueError, TypeError):
                    rating = float(m.group(1))
                break
            # Fallback: "4.7 (3,901)" format
            m2 = re.search(r"(\d+\.?\d*)\s*\(([\d,]+)\)", label)
            if m2:
                try:
                    rating = float(m2.group(1))
                    review_count = int(m2.group(2).replace(",", ""))
                except (ValueError, TypeError):
                    pass
                break

        # Extract address and category from text lines
        address = None
        category = None
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for line in lines:
            if line == name or re.match(r"\d+\.?\d*\(", line):
                continue
            if "·" in line:
                parts = [p.strip() for p in line.split("·") if p.strip()]
                if parts:
                    category = category if category else parts[0]
                    for p in reversed(parts):
                        if p and not re.match(r"^(Open|Closed|Closes)", p, re.I):
                            address = p
                            break
                break

        if name and not _is_placeholder_name(name):
            results.append(
                {
                    "url": url,
                    "name": name,
                    "rating": rating,
                    "review_count": review_count,
                    "address": address,
                    "category": category,
                }
            )

    return results


async def _extract_from_side_panel(
    page: Page,
    feed_item: dict[str, Any],
    logger: Any,
) -> MapsBusiness | None:
    """Click a feed item to open the side panel and extract phone/website/review_count.

    Google Maps search results show a side panel when you click a result.
    This panel loads phone, website, and full address via XHR and renders
    them in the DOM.  We click the item, wait for the panel to load,
    extract the data, then close the panel via the back button.
    """
    place_url = feed_item.get("url", "")
    data: dict[str, Any] = dict(feed_item)  # Start with feed metadata

    try:
        if not place_url or "/place/" not in place_url:
            logger.debug("google_maps.invalid_place_url")
            if data.get("name") and not _is_placeholder_name(data["name"]):
                return _make_maps_business(data, place_url)
            return None

        # Find and click the feed item using Playwright's locator (auto-scrolls into view)
        # JS-side link.click() doesn't scroll, so we use Playwright's native locator.
        # The path segment from the URL is already URL-encoded, so we use it directly
        # without re-encoding (which would double-encode the % characters).
        url_path = urllib.parse.urlparse(place_url).path
        path_segment = url_path.split("/place/")[1].split("/")[0]
        locator = page.locator(f'a[href*="{path_segment}"]').first
        try:
            await locator.click(timeout=5000)
        except Exception:
            logger.debug("google_maps.side_panel_click_failed")
            if data.get("name") and not _is_placeholder_name(data["name"]):
                return _make_maps_business(data, place_url)
            return None

        # Wait for side panel to load
        await human_delay(3000, 5000, page=page)

        # Extract phone, website, review_count from side panel DOM
        side_data = await page.evaluate("""
            () => {
                const body = document.body.innerText || '';
                const lines = body.split('\\n').map(l => l.trim()).filter(l => l);
                const result = {};

                // Find phone: look for lines containing phone-like patterns
                // Phone is typically on its own line like: "+44 20 7287 2200"
                for (const line of lines) {
                    const digits = line.replace(/\\D/g, '');
                    if (digits.length >= 7 && digits.length <= 20 &&
                        !line.includes('stars') && !line.includes('Review') &&
                        !line.includes('£') && !line.includes('Open') &&
                        !line.includes('Close') && !line.includes('https://') &&
                        line.trim().length < 30
                    ) {
                        // Ensure it has phone-like characters (starts with + or is all digits)
                        if (/^\\+[\\d\\s\\-()]+$/.test(line.trim()) || /^[\\d\\s\\-()]+$/.test(line.trim())) {
                            result.phone = line.trim();
                            break;
                        }
                    }
                }

                // Find website: lines with domain names (not Google)
                for (const line of lines) {
                    if ((line.includes('.com') || line.includes('.co.uk') ||
                         line.includes('.net') || line.includes('.org') ||
                         line.includes('.io') || line.includes('.de') ||
                         line.includes('.fr') || line.includes('.it') ||
                         line.includes('.es') || line.includes('.eu')) &&
                        !line.includes('google') &&
                        !line.includes('gstatic') &&
                        !line.includes('maps') &&
                        !line.includes('fontawesome') &&
                        line.length < 80 &&
                        !line.includes(' ')  // Must be a single token
                    ) {
                        result.website = line.startsWith('http') ? line : 'https://' + line;
                        break;
                    }
                }

                // Find review count: lines like "(15,287)"
                for (const line of lines) {
                    const m = line.match(/^\\(([\\d,]+)\\)/);
                    if (m) {
                        try {
                            result.review_count = parseInt(m[1].replace(/,/g, ''));
                        } catch(e) {}
                        break;
                    }
                }

                // Find full address from side panel
                for (const line of lines) {
                    if (/^[\\w\\s]+,\\s*[\\w\\s]+,\\s*[A-Z][A-Z0-9]/.test(line) &&
                        !line.includes('google') &&
                        line.length > 20 &&
                        !line.includes('https://')) {
                        result.address = line;
                        break;
                    }
                }

                return result;
            }
        """)

        if side_data:
            # Merge side panel data into feed metadata (side panel enriches feed data)
            if side_data.get("phone") and not data.get("phone"):
                data["phone"] = side_data["phone"]
            if (
                side_data.get("website")
                and not data.get("website")
                and not _is_platform_url(side_data["website"])
            ):
                data["website"] = side_data["website"]
            if side_data.get("review_count") and not data.get("review_count"):
                data["review_count"] = side_data["review_count"]
            if side_data.get("address") and not data.get("address"):
                data["address"] = side_data["address"]

        # Try to close side panel by pressing Escape or clicking back
        try:
            await page.keyboard.press("Escape")
            await human_delay(500, 1000, page=page)
        except Exception:
            pass

    except Exception as exc:
        logger.debug("google_maps.side_panel_extraction_failed", error=str(exc))

    # Build result from whatever we have
    if data.get("name") and not _is_placeholder_name(data["name"]):
        return _make_maps_business(data, place_url)

    # Last resort: extract name from URL path
    name = _extract_name_from_url(place_url)
    if name:
        return _make_maps_business({"name": name}, place_url)

    return None


def _extract_name_from_url(url: str) -> str | None:
    """Extract business name from Google Maps place URL path.

    URL format: https://www.google.com/maps/place/Business+Name/@...
    """
    try:
        match = re.search(r"/place/([^/@]+)", url)
        if match:
            name = urllib.parse.unquote_plus(match.group(1))
            name = name.replace("+", " ").replace("-", " ").strip()
            if name and name not in ("Google Maps", "Map", "Maps"):
                return name
    except Exception:
        pass
    return None


def _make_maps_business(data: dict[str, Any], url: str) -> MapsBusiness:
    """Convert extracted data dict into MapsBusiness."""
    # Parse external ID from URL
    external_id = "google_maps:unknown"
    match = re.search(r"!1s([^!]+)!", url)
    if match:
        external_id = f"google_maps:{match.group(1)}"

    # Parse lat/lon from URL
    lat, lon = None, None
    coord_match2 = re.search(r"@(-?[\d.]+),(-?[\d.]+)", url)
    if coord_match2:
        with contextlib.suppress(Exception):
            lat, lon = float(coord_match2.group(1)), float(coord_match2.group(2))

    return MapsBusiness(
        external_id=external_id,
        name=data.get("name", ""),
        category=data.get("category"),
        phone=_normalize_phone(data.get("phone")),
        website=data.get("website"),
        address=data.get("address"),
        rating=data.get("rating"),
        review_count=data.get("review_count"),
        latitude=lat,
        longitude=lon,
        source="GOOGLE_MAPS",
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30, jitter=3),
    after=after_log(logger, logging.WARNING),
    reraise=True,
)
async def _retrying_search(keyword: str, location: str) -> list[MapsBusiness]:
    """Retry wrapper for search_google_maps with circuit breaker."""
    circuit = await get_circuit_breaker("google_maps")

    if not await circuit.can_execute():
        raise CircuitOpenError(
            "Circuit breaker open for google_maps",
            source="google_maps",
        )

    try:
        return await circuit.execute(_do_search_google_maps(keyword, location))
    except CircuitOpenError:
        raise


async def _do_search_google_maps(keyword: str, location: str) -> list[MapsBusiness]:
    """Core search with human-like behavior for no-proxy operation."""
    results: list[MapsBusiness] = []
    source = "google_maps"
    start_time = time.monotonic()

    url = f"https://www.google.com/maps/search/{keyword}+{location}"
    scraper_metrics.record_scrape_start(source)

    try:
        async with async_playwright() as p:
            settings = get_settings()
            browser = await p.chromium.launch(
                headless=settings.playwright_headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            ua = random.choice(_USER_AGENTS)
            viewport = random.choice(_VIEWPORTS)
            context = await browser.new_context(
                user_agent=ua,
                viewport=viewport,
                locale="en-US",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            page = await context.new_page()

            # Block only analytics trackers, keep images/CSS for realism
            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}",
                lambda route: (
                    route.abort()
                    if any(
                        d in route.request.url.lower()
                        for d in [
                            "analytics",
                            "tracking",
                            "pixel",
                            "google-analytics",
                            "gtag",
                            "facebook.com/tr",
                        ]
                    )
                    else route.continue_()
                ),
            )

            # Override WebDriver detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await human_delay(2500, 5000, page=page)

                content = await page.content()
                if _check_for_block(content):
                    scraper_metrics.record_scrape_failure(source, "blocked", 0)
                    logger.warning(
                        "google_maps.blocked", keyword=keyword, location=location, url=url
                    )
                    return []

                try:
                    await human_scroll(page, random.randint(100, 300), max_steps=3)
                    await human_delay(1000, 2000, page=page)
                    await human_scroll(page, random.randint(-100, -50), max_steps=2)
                except Exception:
                    pass

                try:
                    await page.wait_for_selector(
                        '[role="feed"], [aria-label*="Results"], [aria-label*="map"], a[href*="/maps/place/"]',
                        timeout=20000,
                    )
                except Exception:
                    logger.warning("google_maps.no_feed", keyword=keyword, location=location)
                    return []

                await human_delay(1500, 3000, page=page)

                feed_items = await _collect_place_urls(page, max_scrolls=6)
                logger.info(
                    "google_maps.scroll_complete",
                    keyword=keyword,
                    location=location,
                    result_count=len(feed_items),
                )

                # Click each feed item to open the side panel — this is where
                # Google Maps loads phone/website/review_count via XHR.
                # Feed metadata (from ARIA labels) provides name/rating/address.
                max_results = min(len(feed_items), settings.scraper_max_results_per_search)
                for i, item in enumerate(feed_items[:max_results]):
                    try:
                        biz = await _extract_from_side_panel(page, item, logger)
                        if biz and biz.name and not _is_placeholder_name(biz.name):
                            results.append(biz)
                            logger.debug(
                                "google_maps.result_extracted",
                                index=i,
                                name=biz.name,
                                rating=biz.rating,
                                phone=biz.phone if biz.phone else None,
                                website=biz.website if biz.website else None,
                            )
                    except Exception as exc:
                        logger.debug("google_maps.result_error", index=i, error=str(exc))
                        continue

            finally:
                await browser.close()

        duration_ms = int((time.monotonic() - start_time) * 1000)
        scraper_metrics.record_scrape_success(source, duration_ms)
        logger.info(
            "google_maps.search_complete",
            keyword=keyword,
            location=location,
            results_found=len(results),
            duration_ms=duration_ms,
        )
        return results

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        scraper_metrics.record_scrape_failure(source, type(exc).__name__, duration_ms)
        logger.exception(
            "google_maps.search_failed",
            keyword=keyword,
            location=location,
            duration_ms=duration_ms,
            error=str(exc),
        )
        raise


async def search_google_maps(keyword: str, location: str) -> list[MapsBusiness]:
    """Main entry point — search Google Maps with self-healing infrastructure.

    Implements a 300-second timeout for the entire operation.
    """
    try:
        return await asyncio.wait_for(
            _retrying_search(keyword, location),
            timeout=300.0,
        )
    except TimeoutError:
        logger.warning(
            "google_maps.timeout",
            keyword=keyword,
            location=location,
            timeout_seconds=300,
        )
        return []
    except CircuitOpenError as exc:
        logger.warning(
            "google_maps.circuit_open",
            keyword=keyword,
            location=location,
            error=str(exc),
        )
        return []
    except Exception as exc:
        logger.exception(
            "google_maps.unexpected_error",
            keyword=keyword,
            location=location,
            error=str(exc),
        )
        return []
