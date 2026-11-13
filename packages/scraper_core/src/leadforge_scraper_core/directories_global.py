"""Refactored global directory scrapers (Yelp, Yell UK) with self-healing infrastructure.

All scrapers use:
  - Circuit breaker per source
  - Extraction strategy pipeline (structured → selector → regex)
  - Enhanced fetch_html with retry, rate limiting, caching
  - Structured logging with full context
"""

from __future__ import annotations

import re
import time
from urllib.parse import quote_plus

import structlog
from leadforge_shared.utils import make_ext_id
from selectolax.lexbor import LexborHTMLParser as HTMLParser
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from leadforge_scraper_core import metrics as scraper_metrics
from leadforge_scraper_core.base import fetch_html
from leadforge_scraper_core.google_maps import MapsBusiness
from leadforge_scraper_core.monitors.circuit_breaker import get_circuit_breaker
from leadforge_scraper_core.strategies import (
    RegexStrategy,
    SelectorStrategy,
    StrategyResult,
    StructuredDataStrategy,
    create_pipeline,
)

logger = structlog.get_logger("scraper.directories_global")

_pipeline = create_pipeline(
    [
        StructuredDataStrategy(),
        SelectorStrategy(),
        RegexStrategy(),
    ]
)


async def _run_extraction_pipeline(
    html: str,
    url: str,
    source_label: str,
) -> StrategyResult | None:
    """Run the extraction strategy pipeline and return merged result."""
    best: StrategyResult | None = None
    for strategy in _pipeline:
        try:
            result = await strategy.extract(html, url, logger=logger)
            if result:
                best = best.merge_with(result) if best else result
        except Exception as exc:
            logger.debug(
                "global_dir.strategy_failed",
                source=source_label,
                strategy=strategy.name,
                error=str(exc),
            )
            continue
    return best


async def _search_with_retry(
    url: str,
    source_label: str,
    keyword: str,
    location: str,
    use_playwright: bool = False,
) -> list[MapsBusiness]:
    """Generic search with circuit breaker, retry, and pipeline extraction."""
    circuit = await get_circuit_breaker(source_label)
    start_time = time.monotonic()
    scraper_metrics.record_scrape_start(source_label)

    if not await circuit.can_execute():
        logger.warning("global_dir.circuit_open", source=source_label)
        return []

    try:
        html = await fetch_html(
            url,
            use_playwright=use_playwright,
            keyword=keyword,
            location=location,
            source=source_label,
        )

        if not html:
            scraper_metrics.record_scrape_failure(source_label, "no_html", 0)
            await circuit.record_failure(Exception("no_html"))
            return []

        result = await _run_extraction_pipeline(html, url, source_label)

        if result and result.name:
            biz = MapsBusiness(
                external_id=make_ext_id(source_label, result.name),
                name=result.name,
                phone=result.phone or None,
                website=result.website or None,
                address=result.address or None,
                rating=result.rating,
                review_count=result.review_count,
                source=source_label.upper(),
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)
            scraper_metrics.record_scrape_success(source_label, duration_ms)
            await circuit.record_success()
            return [biz]

        # CSS fallback
        tree = HTMLParser(html)
        results: list[MapsBusiness] = []
        for node in tree.css(
            "[data-testid='serp-result'], .businessResult__373c0__1Bk0N, .container__373c0__1NUiT, [class*='businessResult'], .listing__373c0__1TIje"
        ):
            try:
                name_el = node.css_first("[data-testid='businessName'], h4, h3, a[href*='/biz/']")
                if not name_el:
                    continue
                name = name_el.text(strip=True)
                if not name or len(name) < 2:
                    continue

                biz_link = node.css_first("a[href*='/biz/']")
                ext_id = make_ext_id(source_label, name)
                if biz_link:
                    href = biz_link.attrs.get("href", "") or ""
                    m = re.search(r"/biz/([^?/#]+)", href)
                    if m:
                        ext_id = f"{source_label}:{m.group(1)}"

                results.append(
                    MapsBusiness(
                        external_id=ext_id,
                        name=name,
                        source=source_label.upper(),
                    )
                )
            except Exception:
                continue

        duration_ms = int((time.monotonic() - start_time) * 1000)
        if results:
            scraper_metrics.record_scrape_success(source_label, duration_ms)
            await circuit.record_success()
        else:
            await circuit.record_failure(Exception("no_results"))
        return results[:20]

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        scraper_metrics.record_scrape_failure(source_label, type(exc).__name__, duration_ms)
        await circuit.record_failure(exc)
        logger.exception(
            "global_dir.search_failed",
            source=source_label,
            keyword=keyword,
            location=location,
            duration_ms=duration_ms,
            error=str(exc),
        )
        return []


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=20, jitter=3),
    reraise=True,
)
async def _retry_yelp(keyword: str, location: str) -> list[MapsBusiness]:
    return await _do_search_yelp(keyword, location)


async def _do_search_yelp(keyword: str, location: str) -> list[MapsBusiness]:
    url = (
        f"https://www.yelp.com/search?"
        f"find_desc={quote_plus(keyword)}&find_loc={quote_plus(location)}"
    )
    return await _search_with_retry(url, "yelp", keyword, location, use_playwright=True)


async def search_yelp(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Yelp for businesses."""
    try:
        return await _do_search_yelp(keyword, location)
    except Exception:
        return []


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=20, jitter=3),
    reraise=True,
)
async def _retry_yell_uk(keyword: str, location: str) -> list[MapsBusiness]:
    return await _do_search_yell_uk(keyword, location)


async def _do_search_yell_uk(keyword: str, location: str) -> list[MapsBusiness]:
    url = (
        f"https://www.yell.com/ucs/UcsSearchAction.do?"
        f"keywords={quote_plus(keyword)}&location={quote_plus(location)}"
    )
    return await _search_with_retry(url, "yell_uk", keyword, location, use_playwright=False)


async def search_yell_uk(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Yell.com UK for businesses."""
    try:
        return await _do_search_yell_uk(keyword, location)
    except Exception:
        return []
