"""Pluggable source registry for country-agnostic business discovery.

Each source function follows the protocol:
    (keyword: str, location: str) -> list[MapsBusiness]

Sources are registered per country (ISO-3166-1 alpha-2).
The "default" key is used when no country-specific list exists.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Coroutine
from typing import Any

from leadforge_config import get_settings

from leadforge_scraper_core.directories import (
    search_cybo_pk,
    search_kompass_pk,
)
from leadforge_scraper_core.directories_country import (
    # FR
    search_annuaire_entreprises,
    search_bizify,
    search_brabys,
    search_canada411,
    # CA
    search_canada_one,
    # DE
    search_das_oertliche,
    search_europages,
    # GB
    search_free_index,
    search_go_yellow,
    # ZA
    search_hellopeter,
    search_indiamart,
    # IN
    search_justdial,
    search_kompass_france,
    # US
    search_manta,
    search_merchant_circle,
    # AE
    search_middle_east_yp,
    search_mymidlist,
    # PK (supplement)
    search_stadtbranchenbuch,
    search_start_local,
    search_streetdirectory,
    search_sulekha,
    search_thomson_local,
    # AU
    search_true_local,
    search_yellowpages_ae,
    # SG
    search_yelu_sg,
)
from leadforge_scraper_core.directories_global import search_yell_uk, search_yelp
from leadforge_scraper_core.google_maps import MapsBusiness, search_google_maps
from leadforge_scraper_core.osm import search_osm

SourceFn = Callable[[str, str], Coroutine[Any, Any, list[MapsBusiness]]]


# ---------------------------------------------------------------------------
# Registry: country (ISO-3166-1 alpha-2) → [(label, callable), ...]
# ---------------------------------------------------------------------------
# "default" is used as the fallback for any country not explicitly listed.
# ---------------------------------------------------------------------------

SOURCE_REGISTRY: dict[str, list[tuple[str, SourceFn]]] = {
    # Default — runs for any country without a specific entry
    "default": [
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # United States
    "US": [
        ("Manta", search_manta),
        ("MerchantCircle", search_merchant_circle),
        ("Yelp", search_yelp),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # United Kingdom
    "GB": [
        ("FreeIndex", search_free_index),
        ("Bizify", search_bizify),
        ("Thomson Local", search_thomson_local),
        ("Yell UK", search_yell_uk),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # Canada
    "CA": [
        ("CanadaOne", search_canada_one),
        ("Canada411", search_canada411),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # Australia
    "AU": [
        ("True Local", search_true_local),
        ("Start Local", search_start_local),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # Germany
    "DE": [
        ("Das Örtliche", search_das_oertliche),
        ("GoYellow", search_go_yellow),
        ("Stadtbranchenbuch", search_stadtbranchenbuch),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # France
    "FR": [
        ("Annuaire des Entreprises", search_annuaire_entreprises),
        ("Kompass France", search_kompass_france),
        ("Europages", search_europages),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # India
    "IN": [
        ("JustDial", search_justdial),
        ("Sulekha", search_sulekha),
        ("IndiaMART", search_indiamart),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # United Arab Emirates
    "AE": [
        ("Middle East Yellow Pages", search_middle_east_yp),
        ("Yellowpages.ae", search_yellowpages_ae),
        ("MyMidlist", search_mymidlist),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # Singapore
    "SG": [
        ("Yelu.sg", search_yelu_sg),
        ("Streetdirectory.com", search_streetdirectory),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # South Africa
    "ZA": [
        ("HelloPeter", search_hellopeter),
        ("Brabys", search_brabys),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
    # Pakistan — only sources that resolve and return real listings.
    # Removed: yellowpages.com.pk / hotfrog.pk (NXDOMAIN),
    #          ypages.pk / mulk.pk / pakbusinessworld.com (JS-rendered pages
    #          that only yield site titles), so they are not enabled by default.
    "PK": [
        ("Cybo PK", search_cybo_pk),
        ("Kompass PK", search_kompass_pk),
        ("Google Maps", search_google_maps),
        ("OpenStreetMap", search_osm),
    ],
}


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")


def _parse_enabled_sources(raw: str) -> dict[str, set[str]]:
    """Parse ``"PK=yellow_pages_pk,hotfrog_pk;US=yelp"`` into per-country slugs."""
    mapping: dict[str, set[str]] = {}
    for chunk in raw.split(";"):
        if "=" not in chunk:
            continue
        code, labels = chunk.split("=", 1)
        slugs = {_slug(label) for label in labels.split(",") if label.strip()}
        if code.strip() and slugs:
            mapping[code.strip().upper()] = slugs
    return mapping


def get_sources_for_country(country_code: str | None) -> list[tuple[str, SourceFn]]:
    """Return the source list for a country code.

    Falls back to ``"default"`` when the code is unknown or None.
    ``ENABLED_SOURCES`` (e.g. ``"US=yelp,google_maps"``) narrows a country's
    list when configured; countries without an entry keep all sources.
    """
    key = country_code.upper() if country_code else ""
    sources = list(SOURCE_REGISTRY.get(key, SOURCE_REGISTRY["default"]))

    enabled = _parse_enabled_sources(get_settings().enabled_sources)
    allowed = enabled.get(key)
    if not allowed:
        return sources
    return [(label, fn) for label, fn in sources if _slug(label) in allowed]


def get_registered_countries() -> list[str]:
    """Return sorted list of registered country codes (excluding 'default')."""
    return sorted(k for k in SOURCE_REGISTRY if k != "default")


def register_source(
    country_code: str,
    label: str,
    fn: SourceFn,
    *,
    prepend: bool = False,
) -> None:
    """Register a new source function for a country code at runtime.

    Args:
        country_code: ISO-3166-1 alpha-2 code (e.g. "DE", "FR", "JP").
        label: Human-readable label for logging.
        fn: Async callable that accepts keyword & location and returns a list of MapsBusiness.
        prepend: If True, insert at the beginning so it runs before other sources.
    """
    key = country_code.upper()
    if key not in SOURCE_REGISTRY:
        SOURCE_REGISTRY[key] = list(SOURCE_REGISTRY["default"])
    entry = (label, fn)
    if prepend:
        SOURCE_REGISTRY[key].insert(0, entry)
    else:
        SOURCE_REGISTRY[key].append(entry)
