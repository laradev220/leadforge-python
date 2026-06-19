"""Scraper core entrypoint. Mirrors packages/scraper-core/src/index.ts."""

from __future__ import annotations

import httpx

from leadforge_scraper_core.contact import (
    ExtractedContact,
    crawl_website,
    extract_contacts,
    get_priority_urls,
)
from leadforge_scraper_core.google_maps import MapsBusiness
from leadforge_scraper_core.social import (
    ExtractedSocial,
    extract_social_profiles,
    scrape_social_profile_for_contacts,
)
from leadforge_scraper_core.source_registry import get_sources_for_country
from leadforge_scraper_core.website import WebsiteAnalysis, analyze_website


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
                    return (
                        reverse.json()
                        .get("address", {})
                        .get("country_code", "")
                        .upper()
                    )
    except Exception:
        pass
    return None


async def search_businesses(
    keyword: str,
    location: str,
    country: str | None = None,
) -> list[MapsBusiness]:
    """Discover businesses from all registered sources for the given country.

    Args:
        keyword: Business category or keyword (e.g. "Dentist", "Restaurant").
        location: City / area string (e.g. "Houston", "London", "Lahore").
        country: ISO-3166-1 alpha-2 country code. When ``None``, the country
                 is inferred from *location* via Nominatim geocoding.

    Returns:
        Up to 20 deduplicated ``MapsBusiness`` records.
    """
    resolved_country = country or await _guess_country(location)
    sources = get_sources_for_country(resolved_country)

    all_results: list[MapsBusiness] = []
    for _label, fn in sources:
        try:
            batch = await fn(keyword, location)
            if batch:
                all_results.extend(batch)
        except Exception:
            pass

    # Dedup by external_id — first occurrence wins
    seen: set[str] = set()
    final: list[MapsBusiness] = []
    for b in all_results:
        if b.external_id not in seen:
            final.append(b)
            seen.add(b.external_id)

    return final[:20]


__all__ = [
    "search_businesses",
    "MapsBusiness",
    "analyze_website",
    "WebsiteAnalysis",
    "extract_contacts",
    "crawl_website",
    "get_priority_urls",
    "ExtractedContact",
    "extract_social_profiles",
    "ExtractedSocial",
    "scrape_social_profile_for_contacts",
]
