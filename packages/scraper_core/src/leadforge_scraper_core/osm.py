"""OSM Overpass fallback. Mirrors packages/scraper-core/src/sources/osm.ts."""

from __future__ import annotations

import httpx

from leadforge_scraper_core.google_maps import MapsBusiness


async def search_osm(keyword: str, location: str) -> list[MapsBusiness]:
    try:
        async with httpx.AsyncClient() as client:
            geo_res = await client.get(
                f"https://nominatim.openstreetmap.org/search?q={keyword} {location}&format=json&limit=1"
            )
            if geo_res.status_code != 200:
                return []
            geo_data = geo_res.json()
            if not geo_data:
                return []

            lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]

            query = f"""[out:json][timeout:25];
            (
                node["name"~"{keyword}",i](around:10000, {lat}, {lon});
                way["name"~"{keyword}",i](around:10000, {lat}, {lon});
                relation["name"~"{keyword}",i](around:10000, {lat}, {lon});
            );
            out center;"""

            res = await client.post(
                "https://overpass.openstreetmap.fr/api/interpreter", data={"data": query}
            )
            if res.status_code != 200:
                return []
            elements = res.json().get("elements", [])

            return [
                MapsBusiness(
                    external_id=f"openstreetmap:{el['id']}",
                    name=el["tags"].get("name", "Unknown"),
                    category=el["tags"].get("shop") or el["tags"].get("amenity") or "Business",
                    address=f"{el['tags'].get('addr:street', '')} {el['tags'].get('addr:city', location)}".strip(),
                    phone=el["tags"].get("contact:phone") or el["tags"].get("phone"),
                    website=el["tags"].get("website"),
                    latitude=el.get("lat") or el.get("center", {}).get("lat"),
                    longitude=el.get("lon") or el.get("center", {}).get("lon"),
                    source="OSM",
                )
                for el in elements
            ]
    except Exception:
        return []
