"""Refactored directory scrapers using multi-strategy extraction pipeline.

Each scraper composes the extraction strategies (structured, selector, regex)
and adds its own circuit breaker.  All use the enhanced base.py fetch_html.
"""

from __future__ import annotations

import time

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

logger = structlog.get_logger("scraper.directories")

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
                "directory.strategy_failed",
                source=source_label,
                strategy=strategy.name,
                error=str(exc),
            )
            continue
    return best


async def _search_directory(
    keyword: str,
    location: str,
    url: str,
    source_label: str,
    name_selectors: list[str],
) -> list[MapsBusiness]:
    """Generic directory search with retry and circuit breaker."""
    circuit = await get_circuit_breaker(source_label)
    start_time = time.monotonic()
    scraper_metrics.record_scrape_start(source_label)

    try:
        if not await circuit.can_execute():
            logger.warning("directory.circuit_open", source=source_label, url=url)
            return []

        html = await fetch_html(
            url,
            use_playwright=False,
            keyword=keyword,
            location=location,
            source=source_label,
        )

        if not html:
            scraper_metrics.record_scrape_failure(source_label, "no_html", 0)
            return []

        # Run extraction pipeline
        result = await _run_extraction_pipeline(html, url, source_label)

        if result and result.name:
            business = MapsBusiness(
                external_id=make_ext_id(source_label, result.name),
                name=result.name,
                phone=result.phone or None,
                website=result.website or None,
                address=result.address or None,
                source="DIRECTORY",
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)
            scraper_metrics.record_scrape_success(source_label, duration_ms)
            return [business]

        # Fall back to basic CSS extraction if pipeline returned nothing
        tree = HTMLParser(html)
        results: list[MapsBusiness] = []
        for node in tree.css(".business-listing, .result, .listing, [class*='listing']"):
            try:
                name_el = node.css_first("h2, .title, .name, h3")
                if not name_el:
                    continue
                name = name_el.text(strip=True)
                if not name or len(name) < 2:
                    continue
                biz = MapsBusiness(
                    external_id=make_ext_id(source_label, name),
                    name=name,
                    source="DIRECTORY",
                )
                results.append(biz)
            except Exception:
                continue

        duration_ms = int((time.monotonic() - start_time) * 1000)
        if results:
            scraper_metrics.record_scrape_success(source_label, duration_ms)
        return results[:20]

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        scraper_metrics.record_scrape_failure(source_label, type(exc).__name__, duration_ms)
        await circuit.record_failure(exc)
        logger.exception(
            "directory.search_failed",
            source=source_label,
            keyword=keyword,
            location=location,
            url=url,
            duration_ms=duration_ms,
            error=str(exc),
        )
        return []
    finally:
        await circuit.record_success()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=15, jitter=2),
    reraise=True,
)
async def _retry_fetch(url: str, source_label: str, keyword: str, location: str) -> str | None:
    return await fetch_html(url, source=source_label, keyword=keyword, location=location)


async def search_yellow_pages_pk(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Yellow Pages Pakistan for businesses."""
    url = f"https://www.yellowpages.com.pk/search.php?what={keyword}&where={location}"
    try:
        return await _search_directory(
            keyword,
            location,
            url,
            source_label="yellowpages_pk",
            name_selectors=[".business-listing h2", ".result .title"],
        )
    except Exception:
        return []


async def search_hotfrog_pk(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Hotfrog Pakistan for businesses."""
    url = f"https://www.hotfrog.pk/search?q={keyword}&location={location}"
    try:
        return await _search_directory(
            keyword,
            location,
            url,
            source_label="hotfrog_pk",
            name_selectors=[".business-listing .title", ".listing h3"],
        )
    except Exception:
        return []


async def search_cybo_pk(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Cybo Pakistan for businesses."""
    url = f"https://www.cybo.com/Pakistan/?search={keyword}&location={location}"
    try:
        return await _search_directory(
            keyword,
            location,
            url,
            source_label="cybo_pk",
            name_selectors=[".business-listing .title", ".listing h2"],
        )
    except Exception:
        return []


async def search_kompass_pk(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Kompass for businesses."""
    url = f"https://www.kompass.com/en/search/companies?text={keyword}&location={location}"
    try:
        return await _search_directory(
            keyword,
            location,
            url,
            source_label="kompass_pk",
            name_selectors=[".company-item h3", ".result .company-name"],
        )
    except Exception:
        return []
