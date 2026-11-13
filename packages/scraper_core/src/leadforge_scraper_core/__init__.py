"""Scraper core entrypoint. Mirrors packages/scraper-core/src/index.ts."""

from __future__ import annotations

import httpx
import structlog
from leadforge_config import get_settings

from leadforge_scraper_core.contact import (
    ExtractedContact,
    crawl_website,
    extract_contacts,
    get_priority_urls,
)
from leadforge_scraper_core.google_maps import MapsBusiness
from leadforge_scraper_core.social import (
    ExtractedSocial,
    RichProfileData,
    extract_rich_profile_data,
    extract_social_profiles,
    scrape_social_profile_for_contacts,
    scrape_social_profile_rich,
)
from leadforge_scraper_core.source_registry import get_sources_for_country
from leadforge_scraper_core.website import WebsiteAnalysis, analyze_website

logger = structlog.get_logger("scraper.registry")


async def _guess_country(location: str) -> str | None:
    """Geocode *location* via Nominatim and return ISO-3166-1 alpha-2 code.

    Returns None when geocoding fails (falls back to ``"default"`` sources).
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": location, "format": "json", "limit": 1},
                headers={"User-Agent": "LeadForge/1.0"},
            )
            if resp.status_code == 200 and resp.json():
                data = resp.json()[0]
                lat, lon = data["lat"], data["lon"]
                reverse = await client.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"lat": lat, "lon": lon, "format": "json"},
                    headers={"User-Agent": "LeadForge/1.0"},
                )
                if reverse.status_code == 200:
                    return reverse.json().get("address", {}).get("country_code", "").upper()
    except Exception:
        pass
    return None


async def search_businesses(
    keyword: str,
    location: str,
    country: str | None = None,
    max_per_source: int | None = None,
) -> list[MapsBusiness]:
    """Discover businesses from all enabled sources for the given country.

    Args:
        keyword: Business category or keyword (e.g. "Dentist", "Restaurant").
        location: City / area string (e.g. "Houston", "London", "Lahore").
        country: ISO-3166-1 alpha-2 country code. When ``None``, the country
                 is inferred from *location* via Nominatim geocoding.
        max_per_source: Cap per source (defaults to ``SCRAPER_MAX_RESULTS_PER_SEARCH``).

    Returns deduplicated ``MapsBusiness`` records. A failing source is logged
    and skipped instead of silently disappearing.
    """
    resolved_country = (country or await _guess_country(location) or "").upper() or None
    sources = get_sources_for_country(resolved_country)
    limit = max_per_source or get_settings().scraper_max_results_per_search

    all_results: list[MapsBusiness] = []
    for label, fn in sources:
        try:
            batch = await fn(keyword, location)
        except Exception as exc:
            logger.warning(
                "source_failed",
                source=label,
                keyword=keyword,
                location=location,
                error=str(exc),
            )
            continue
        if batch:
            all_results.extend(batch[:limit])

    # Dedup by external_id — first occurrence wins
    seen: set[str] = set()
    final: list[MapsBusiness] = []
    for b in all_results:
        if b.external_id not in seen:
            final.append(b)
            seen.add(b.external_id)

    logger.info(
        "search_completed",
        keyword=keyword,
        location=location,
        country=resolved_country,
        sources=len(sources),
        results=len(final),
    )
    return final


__all__ = [
    "ExtractedContact",
    "ExtractedSocial",
    "MapsBusiness",
    "RichProfileData",
    "WebsiteAnalysis",
    "analyze_website",
    "crawl_website",
    "extract_contacts",
    "extract_rich_profile_data",
    "extract_social_profiles",
    "get_priority_urls",
    "scrape_social_profile_for_contacts",
    "scrape_social_profile_rich",
    "search_businesses",
]
