"""OSM Overpass fallback. Mirrors packages/scraper-core/src/sources/osm.ts.

Nominatim is used to geocode the *location* (never keyword + location), then
Overpass is queried with tag filters derived from the keyword. Public Overpass
instances reject requests without a User-Agent and some mirrors now require
whitelisting, so endpoints are tried in order.
"""

from __future__ import annotations

import asyncio

import httpx
import structlog

from leadforge_scraper_core.google_maps import MapsBusiness

logger = structlog.get_logger("scraper.osm")

_HEADERS = {
    "User-Agent": "LeadForge/1.0 (business lead enrichment)",
    "Accept": "application/json",
}
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
_RADIUS_M = 10_000

# Keyword -> Overpass tag filter. Falls back to a name regex for unknown terms.
_TAG_FILTERS: dict[str, str] = {
    "restaurant": '["amenity"="restaurant"]',
    "cafe": '["amenity"="cafe"]',
    "coffee": '["amenity"="cafe"]',
    "fast food": '["amenity"="fast_food"]',
    "bakery": '["shop"="bakery"]',
    "dentist": '["amenity"="dentist"]',
    "doctor": '["amenity"="doctors"]',
    "hospital": '["amenity"="hospital"]',
    "clinic": '["amenity"="clinic"]',
    "pharmacy": '["amenity"="pharmacy"]',
    "hotel": '["tourism"="hotel"]',
    "school": '["amenity"="school"]',
    "bank": '["amenity"="bank"]',
    "gym": '["leisure"="fitness_centre"]',
    "salon": '["shop"="hairdresser"]',
    "barber": '["shop"="hairdresser"]',
    "supermarket": '["shop"="supermarket"]',
    "car repair": '["shop"="car_repair"]',
    "lawyer": '["office"="lawyer"]',
    "real estate": '["office"="estate_agent"]',
    "travel agency": '["office"="travel_agent"]',
}


def _tag_filter(keyword: str) -> str:
    key = keyword.strip().lower()
    if key in _TAG_FILTERS:
        return _TAG_FILTERS[key]
    for name, tag_filter in _TAG_FILTERS.items():
        if name in key or key in name:
            return tag_filter
    safe = keyword.replace('"', "").replace("\\", "")
    return f'["name"~"{safe}",i]'


def _to_business(element: dict) -> MapsBusiness | None:
    tags = element.get("tags") or {}
    name = tags.get("name")
    if not name:
        return None
    street = tags.get("addr:street", "")
    city = tags.get("addr:city", "")
    address = ", ".join(part for part in (street, city) if part) or None

    return MapsBusiness(
        external_id=f"openstreetmap:{element.get('type', 'node')}:{element['id']}",
        name=name,
        category=(
            tags.get("amenity")
            or tags.get("shop")
            or tags.get("craft")
            or tags.get("tourism")
            or tags.get("office")
            or "Business"
        ),
        address=address,
        city=city or None,
        country=tags.get("addr:country") or None,
        postal_code=tags.get("addr:postcode") or None,
        phone=tags.get("contact:phone") or tags.get("phone"),
        website=tags.get("contact:website") or tags.get("website"),
        latitude=element.get("lat") or (element.get("center") or {}).get("lat"),
        longitude=element.get("lon") or (element.get("center") or {}).get("lon"),
        source="OSM",
    )


async def search_osm(keyword: str, location: str) -> list[MapsBusiness]:
    if not keyword or not location:
        return []

    async with httpx.AsyncClient(timeout=20.0, headers=_HEADERS, follow_redirects=True) as client:
        try:
            geo_res = await client.get(
                _NOMINATIM,
                params={"q": location, "format": "json", "limit": 1},
            )
            if geo_res.status_code != 200:
                logger.warning("osm.geocode_failed", location=location, status=geo_res.status_code)
                return []
            geo_data = geo_res.json()
            if not geo_data:
                logger.warning("osm.geocode_empty", location=location)
                return []
            lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]
        except Exception as exc:
            logger.warning("osm.geocode_error", location=location, error=str(exc))
            return []

        query = (
            "[out:json][timeout:25];"
            f"nwr{_tag_filter(keyword)}(around:{_RADIUS_M},{lat},{lon});"
            "out center 60;"
        )

        # Public Overpass instances are frequently overloaded; retry the
        # mirror list once before giving up.
        for attempt in range(2):
            for endpoint in _OVERPASS_ENDPOINTS:
                try:
                    res = await client.post(endpoint, data={"data": query})
                except Exception as exc:
                    logger.warning("osm.overpass_error", endpoint=endpoint, error=str(exc))
                    continue
                if res.status_code != 200:
                    logger.warning("osm.overpass_status", endpoint=endpoint, status=res.status_code)
                    continue
                try:
                    elements = res.json().get("elements", [])
                except ValueError:
                    continue

                businesses = [b for b in map(_to_business, elements) if b is not None]
                logger.info(
                    "osm.search_complete",
                    keyword=keyword,
                    location=location,
                    endpoint=endpoint,
                    results=len(businesses),
                )
                return businesses
            if attempt == 0:
                await asyncio.sleep(1.5)

    return []
