"""Country-specific business directory scrapers.

Every function follows the ``SourceFn`` protocol:
    (keyword: str, location: str) -> list[MapsBusiness]

Each scraper uses:
  - The circuit breaker per source
  - Extraction strategy pipeline (structured → selector → regex)
  - Enhanced fetch_html with retry, rate limiting, caching
  - Structured logging with full context
"""

from __future__ import annotations

import contextlib
import re
import time
from urllib.parse import quote_plus

import structlog
from leadforge_shared.utils import make_ext_id
from selectolax.lexbor import LexborHTMLParser as HTMLParser

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

logger = structlog.get_logger("scraper.directories_country")

# Shared extraction pipeline
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
                "country_dir.strategy_failed",
                source=source_label,
                strategy=strategy.name,
                error=str(exc),
            )
            continue
    return best


async def _search_directory(
    url: str,
    source_label: str,
    keyword: str,
    location: str,
    *,
    use_playwright: bool = False,
    item_selector: str = "div.result, div.listing, li.result, .business-card, [class*='business'], [class*='listing']",
    name_selector: str = "h2, h3, .title, .name, a[href*='/biz'], .business-name",
    detail_selector: str | None = None,
) -> list[MapsBusiness]:
    """Generic directory search with circuit breaker and extraction pipeline.

    Args:
        url: Fully constructed search URL.
        source_label: Unique source identifier for circuit breaker / metrics.
        keyword: Search keyword.
        location: Search location.
        use_playwright: Whether to use Playwright for JS-heavy sites.
        item_selector: CSS selector for individual result cards/rows.
        name_selector: CSS selector for business name within each result.
        detail_selector: If set, extract business data from this container per item.
    """
    circuit = await get_circuit_breaker(source_label)
    start_time = time.monotonic()
    scraper_metrics.record_scrape_start(source_label)

    try:
        if not await circuit.can_execute():
            logger.warning("country_dir.circuit_open", source=source_label, url=url)
            return []

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

        # Try pipeline extraction first
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

        # Fall back to CSS extraction of result items
        tree = HTMLParser(html)
        results: list[MapsBusiness] = []

        items = tree.css(item_selector)
        if not items:
            # Try broader selectors
            items = tree.css("tr, div.row, .item, article, [data-result]")

        for node in items:
            try:
                container = node
                if detail_selector:
                    detail = node.css_first(detail_selector)
                    if detail:
                        container = detail

                name_el = container.css_first(name_selector)
                if not name_el:
                    continue
                name = name_el.text(strip=True)
                if not name or len(name) < 2:
                    continue

                # Extract optional fields
                phone_el = container.css_first(
                    "[class*='phone'], a[href^='tel:'], [class*='tel'], [itemprop='telephone']"
                )
                phone = phone_el.text(strip=True) if phone_el else None
                if phone and phone.startswith("tel:"):
                    phone = phone[4:]

                website_el = container.css_first(
                    "[class*='website'], a[href^='http'], [itemprop='url']"
                )
                website = None
                if website_el:
                    href = website_el.attrs.get("href", "") or ""
                    # Skip mailto, tel, and page anchors
                    if href.startswith("http"):
                        website = href

                address_el = container.css_first(
                    "[class*='address'], [class*='location'], [itemprop='address'], [class*='street']"
                )
                address = address_el.text(strip=True) if address_el else None

                rating_el = container.css_first(
                    "[class*='rating'], [class*='stars'], [itemprop='ratingValue']"
                )
                rating = None
                if rating_el:
                    with contextlib.suppress(AttributeError, ValueError):
                        match = re.search(
                            r"[\d.]+",
                            rating_el.text(strip=True),
                        )
                        if match:
                            rating = float(match.group(0))

                reviews_el = container.css_first("[class*='review'], [itemprop='reviewCount']")
                review_count = None
                if reviews_el:
                    with contextlib.suppress(AttributeError, ValueError):
                        match = re.search(
                            r"[\d,]+",
                            reviews_el.text(strip=True).replace(",", ""),
                        )
                        if match:
                            review_count = int(match.group(0))

                biz = MapsBusiness(
                    external_id=make_ext_id(source_label, name),
                    name=name,
                    phone=phone,
                    website=website,
                    address=address,
                    rating=rating,
                    review_count=review_count,
                    source=source_label.upper(),
                )
                results.append(biz)

            except Exception as exc:
                logger.debug(
                    "country_dir.parse_item_failed",
                    source=source_label,
                    error=str(exc),
                )
                continue

        duration_ms = int((time.monotonic() - start_time) * 1000)
        if results:
            scraper_metrics.record_scrape_success(source_label, duration_ms)
            await circuit.record_success()
            logger.info(
                "country_dir.search_complete",
                source=source_label,
                results_found=len(results),
                duration_ms=duration_ms,
            )
        else:
            logger.warning(
                "country_dir.no_results",
                source=source_label,
                url=url,
                duration_ms=duration_ms,
            )
            await circuit.record_failure(Exception("no_results"))
        return results[:20]

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        scraper_metrics.record_scrape_failure(source_label, type(exc).__name__, duration_ms)
        await circuit.record_failure(exc)
        logger.exception(
            "country_dir.search_failed",
            source=source_label,
            keyword=keyword,
            location=location,
            duration_ms=duration_ms,
            error=str(exc),
        )
        return []


# ── United States ─────────────────────────────────────────────────────────────


async def search_manta(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Manta (US) for businesses."""
    url = f"https://www.manta.com/s?search={quote_plus(keyword)}&location={quote_plus(location)}"
    return await _search_directory(
        url,
        "manta",
        keyword,
        location,
        item_selector=".listing-card, .result-item, [class*='listing']",
        name_selector=".listing-title, h3, .name a",
    )


async def search_merchant_circle(keyword: str, location: str) -> list[MapsBusiness]:
    """Search MerchantCircle (US) for businesses."""
    url = f"https://www.merchantcircle.com/search?q={quote_plus(keyword)}+{quote_plus(location)}"
    return await _search_directory(
        url,
        "merchant_circle",
        keyword,
        location,
        item_selector=".listing, .result, [class*='business'], .profile-card",
        name_selector=".title a, h3, .business-name",
    )


# ── United Kingdom ────────────────────────────────────────────────────────────


async def search_free_index(keyword: str, location: str) -> list[MapsBusiness]:
    """Search FreeIndex (GB) for businesses."""
    url = (
        f"https://www.freeindex.co.uk/search.htm?search={quote_plus(keyword)}"
        f"&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "free_index",
        keyword,
        location,
        item_selector=".result, .listing, .business-card",
        name_selector="h3, .title a, .business-name",
    )


async def search_bizify(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Bizify (GB) for businesses."""
    url = f"https://www.bizify.co.uk/search?q={quote_plus(keyword)}&location={quote_plus(location)}"
    return await _search_directory(
        url,
        "bizify",
        keyword,
        location,
        item_selector=".result, .listing, [class*='business']",
        name_selector="h2, h3, .title, .name",
    )


async def search_thomson_local(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Thomson Local (GB) for businesses."""
    url = f"https://www.thomsonlocal.com/search/{quote_plus(keyword)}/{quote_plus(location)}/"
    return await _search_directory(
        url,
        "thomson_local",
        keyword,
        location,
        item_selector=".result, .listing, .business-card, [class*='result']",
        name_selector="h2, h3, .business-name, .name",
    )


# ── Canada ────────────────────────────────────────────────────────────────────


async def search_canada_one(keyword: str, location: str) -> list[MapsBusiness]:
    """Search CanadaOne (CA) for businesses."""
    url = (
        f"https://www.canadaone.com/search/?q={quote_plus(keyword)}&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "canada_one",
        keyword,
        location,
        item_selector=".result, .listing, .business-entry",
        name_selector="h3, .title, .name, a.business-link",
    )


async def search_canada411(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Canada411 (CA) for businesses."""
    url = (
        f"https://www.canada411.ca/search/?stype=bu&what={quote_plus(keyword)}"
        f"&where={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "canada411",
        keyword,
        location,
        item_selector=".result, .listing, .business-listing, .company-result",
        name_selector="h3, .title, .business-name, .name",
    )


# ── Australia ─────────────────────────────────────────────────────────────────


async def search_true_local(keyword: str, location: str) -> list[MapsBusiness]:
    """Search True Local (AU) for businesses."""
    url = f"https://www.truelocal.com.au/find/{quote_plus(keyword)}/{quote_plus(location)}"
    return await _search_directory(
        url,
        "true_local",
        keyword,
        location,
        item_selector=".result, .listing, .business-card, [data-testid*='result']",
        name_selector="h3, h2, .business-name, [class*='name']",
    )


async def search_start_local(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Start Local (AU) for businesses."""
    url = (
        f"https://www.startlocal.com.au/search?q={quote_plus(keyword)}"
        f"&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "start_local",
        keyword,
        location,
        item_selector=".result, .listing, .business-card",
        name_selector="h3, .title a, .business-name",
    )


# ── Germany ───────────────────────────────────────────────────────────────────


async def search_das_oertliche(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Das Örtliche (DE) for businesses."""
    url = (
        f"https://www.dasoertliche.de/?keywords={quote_plus(keyword)}"
        f"&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "das_oertliche",
        keyword,
        location,
        item_selector=".result, .entry, .listing, .treffer, [class*='result']",
        name_selector="h3, h2, .firmenname, .name, .title",
    )


async def search_go_yellow(keyword: str, location: str) -> list[MapsBusiness]:
    """Search GoYellow (DE) for businesses."""
    url = f"https://www.goyellow.de/search?q={quote_plus(keyword)}&location={quote_plus(location)}"
    return await _search_directory(
        url,
        "go_yellow",
        keyword,
        location,
        item_selector=".result, .listing, .business-card, .company-result",
        name_selector="h3, h2, .title, .company-name",
    )


async def search_stadtbranchenbuch(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Stadtbranchenbuch (DE) for businesses."""
    url = (
        f"https://www.stadtbranchenbuch.com/search?q={quote_plus(keyword)}"
        f"&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "stadtbranchenbuch",
        keyword,
        location,
        item_selector=".result, .listing, .company-entry, .eintrag",
        name_selector="h3, h2, .firmenname, .title, .name",
    )


# ── France ────────────────────────────────────────────────────────────────────


async def search_annuaire_entreprises(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Annuaire des Entreprises (FR) for businesses.

    Uses the official French business registry (infogreffe.fr / societe.com).
    """
    url = (
        f"https://www.annuaire-entreprises.data.gouv.fr/rechercher?"
        f"q={quote_plus(keyword)}+{quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "annuaire_entreprises",
        keyword,
        location,
        item_selector=".result, .listing, .company-card, [class*='result'], article",
        name_selector="h3, h2, .title, .company-name, .name",
    )


async def search_kompass_france(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Kompass France for businesses."""
    url = (
        f"https://fr.kompass.com/search/companies?text={quote_plus(keyword)}"
        f"&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "kompass_france",
        keyword,
        location,
        item_selector=".company-item, .result, .card-company, [class*='company']",
        name_selector="h3, .company-name, .title, .name",
    )


async def search_europages(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Europages (FR/EU) for businesses."""
    url = f"https://www.europages.com/search/{quote_plus(keyword)}/{quote_plus(location)}"
    return await _search_directory(
        url,
        "europages",
        keyword,
        location,
        item_selector=".result, .listing, .company-card, [class*='pro'], article",
        name_selector="h3, h2, .company-name, .title, a[class*='name']",
    )


# ── India ─────────────────────────────────────────────────────────────────────


async def search_justdial(keyword: str, location: str) -> list[MapsBusiness]:
    """Search JustDial (IN) for businesses.

    JustDial is JavaScript-heavy so uses Playwright.
    """
    url = f"https://www.justdial.com/search?q={quote_plus(keyword)}&city={quote_plus(location)}"
    return await _search_directory(
        url,
        "justdial",
        keyword,
        location,
        use_playwright=True,
        item_selector=".result, .listing, .card-list, .jcard, [class*='store']",
        name_selector="h2, h3, .lng_cont_name, .title, .store-name, a[class*='name']",
    )


async def search_sulekha(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Sulekha (IN) for businesses.

    Sulekha is JavaScript-heavy so uses Playwright.
    """
    url = f"https://www.sulekha.com/search?q={quote_plus(keyword)}&location={quote_plus(location)}"
    return await _search_directory(
        url,
        "sulekha",
        keyword,
        location,
        use_playwright=True,
        item_selector=".result, .listing, .serp-card, .sc-common, [class*='card']",
        name_selector="h3, h2, .title, .name, .business-name, a[class*='title']",
    )


async def search_indiamart(keyword: str, location: str) -> list[MapsBusiness]:
    """Search IndiaMART (IN) for businesses.

    IndiaMART is JavaScript-heavy so uses Playwright.
    """
    url = (
        f"https://www.indiamart.com/search.html?q={quote_plus(keyword)}&loc={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "indiamart",
        keyword,
        location,
        use_playwright=True,
        item_selector=".result, .listing, .card, .product-item, .company-card, [class*='result']",
        name_selector="h3, h2, .title, .company-name, .vendor-name, a[class*='name']",
    )


# ── United Arab Emirates ──────────────────────────────────────────────────────


async def search_middle_east_yp(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Middle East Yellow Pages (AE) for businesses."""
    url = (
        f"https://www.middleeastyellowpages.com/search?"
        f"q={quote_plus(keyword)}&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "middle_east_yp",
        keyword,
        location,
        item_selector=".result, .listing, .company-result, .card, [class*='business']",
        name_selector="h3, h2, .title, .company-name, .name",
    )


async def search_yellowpages_ae(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Yellowpages.ae (AE) for businesses."""
    url = (
        f"https://www.yellowpages.ae/search?what={quote_plus(keyword)}&where={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "yellowpages_ae",
        keyword,
        location,
        item_selector=".result, .listing, .company-card, .business-listing, [class*='result']",
        name_selector="h3, .title, .company-name, .name, a[class*='company']",
    )


async def search_mymidlist(keyword: str, location: str) -> list[MapsBusiness]:
    """Search MyMidlist (AE) for businesses."""
    url = (
        f"https://www.mymidlist.com/search?q={quote_plus(keyword)}&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "mymidlist",
        keyword,
        location,
        item_selector=".result, .listing, .card, .business-card, [class*='listing']",
        name_selector="h3, h2, .title, .name, .business-name",
    )


# ── Singapore ─────────────────────────────────────────────────────────────────


async def search_yelu_sg(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Yelu.sg (SG) for businesses."""
    url = f"https://yelu.sg/search?q={quote_plus(keyword)}&location={quote_plus(location)}"
    return await _search_directory(
        url,
        "yelu_sg",
        keyword,
        location,
        item_selector=".result, .listing, .card, .business-card, [class*='result']",
        name_selector="h3, h2, .title, .name, .business-name, a[class*='name']",
    )


async def search_streetdirectory(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Streetdirectory.com Business Finder (SG) for businesses."""
    url = (
        f"https://www.streetdirectory.com/businessfinder/search?"
        f"q={quote_plus(keyword)}&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "streetdirectory",
        keyword,
        location,
        item_selector=".result, .listing, .business-result, .card, tr",
        name_selector="h3, h2, .title, .name, a[class*='business'], .company-name",
    )


# ── South Africa ──────────────────────────────────────────────────────────────


async def search_hellopeter(keyword: str, location: str) -> list[MapsBusiness]:
    """Search HelloPeter (ZA) for businesses."""
    url = (
        f"https://www.hellopeter.com/search?q={quote_plus(keyword)}&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "hellopeter",
        keyword,
        location,
        item_selector=".result, .listing, .card, .business-card, [class*='result']",
        name_selector="h3, h2, .title, .name, .business-name",
    )


async def search_brabys(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Brabys (ZA) for businesses."""
    url = f"https://www.brabys.com/search?q={quote_plus(keyword)}&location={quote_plus(location)}"
    return await _search_directory(
        url,
        "brabys",
        keyword,
        location,
        item_selector=".result, .listing, .card, .company-result, [class*='result']",
        name_selector="h3, h2, .title, .company-name, .name",
    )


# ── Pakistan (supplement existing) ────────────────────────────────────────────


async def search_pak_business_world(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Pak Business World (PK) for businesses."""
    url = (
        f"https://www.pakbusinessworld.com/search?"
        f"q={quote_plus(keyword)}&location={quote_plus(location)}"
    )
    return await _search_directory(
        url,
        "pak_business_world",
        keyword,
        location,
        item_selector=".result, .listing, .card, .business-card, [class*='listing']",
        name_selector="h3, h2, .title, .name, .business-name",
    )


async def search_ypages_pk(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Ypages.pk (PK) for businesses."""
    url = f"https://www.ypages.pk/search?what={quote_plus(keyword)}&where={quote_plus(location)}"
    return await _search_directory(
        url,
        "ypages_pk",
        keyword,
        location,
        item_selector=".result, .listing, .business-listing, .card, [class*='result']",
        name_selector="h3, .title, .business-name, .name",
    )


async def search_mulk_pk(keyword: str, location: str) -> list[MapsBusiness]:
    """Search Mulk.pk (PK) for businesses."""
    url = f"https://www.mulk.pk/search?q={quote_plus(keyword)}&location={quote_plus(location)}"
    return await _search_directory(
        url,
        "mulk_pk",
        keyword,
        location,
        item_selector=".result, .listing, .card, .business-card, [class*='listing']",
        name_selector="h3, h2, .title, .name, .business-name",
    )
