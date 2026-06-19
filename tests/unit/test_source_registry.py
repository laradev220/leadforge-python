"""Unit tests for source_registry.py — deduplication fix, country lookup, and source registration.

Validates the critical bug fix: no duplicate PK key in SOURCE_REGISTRY.
"""

from __future__ import annotations

from typing import Any

import pytest

from leadforge_scraper_core.source_registry import (
    SOURCE_REGISTRY,
    get_sources_for_country,
    get_registered_countries,
    register_source,
)


class TestSourceRegistryStructure:
    """Tests for SOURCE_REGISTRY structure and the PK dedup fix."""

    def test_default_key_exists(self) -> None:
        """The 'default' key must exist as a fallback."""
        assert "default" in SOURCE_REGISTRY
        assert len(SOURCE_REGISTRY["default"]) >= 1

    def test_pk_has_no_duplicate_key(self) -> None:
        """PK must appear exactly once (the dedup bug fix)."""
        count = sum(1 for k in SOURCE_REGISTRY if k == "PK")
        assert count == 1, f"PK appears {count} times (should be 1)"

    def test_pk_has_all_sources(self) -> None:
        """PK should have 9 sources after dedup (2 Google+OSM + 7 directories)."""
        pk_sources = SOURCE_REGISTRY["PK"]
        assert len(pk_sources) == 9, f"PK has {len(pk_sources)} sources, expected 9"

    def test_pk_includes_directory_sources(self) -> None:
        """PK should include Pakistan-specific directories (not just Google Maps + OSM)."""
        pk_labels = {label for label, _ in SOURCE_REGISTRY["PK"]}
        assert "Yellow Pages PK" in pk_labels
        assert "Hotfrog PK" in pk_labels
        assert "Cybo PK" in pk_labels
        assert "Kompass PK" in pk_labels
        assert "Pak Business World" in pk_labels
        assert "Ypages.pk" in pk_labels
        assert "Mulk.pk" in pk_labels

    def test_pk_includes_google_maps(self) -> None:
        """PK should still include Google Maps."""
        pk_labels = {label for label, _ in SOURCE_REGISTRY["PK"]}
        assert "Google Maps" in pk_labels

    def test_pk_includes_osm(self) -> None:
        """PK should still include OpenStreetMap."""
        pk_labels = {label for label, _ in SOURCE_REGISTRY["PK"]}
        assert "OpenStreetMap" in pk_labels

    def test_all_registered_countries_have_default_sources(self) -> None:
        """Every country-specific entry should include at least Google Maps + OSM."""
        for country, sources in SOURCE_REGISTRY.items():
            if country == "default":
                continue
            labels = {label for label, _ in sources}
            assert "Google Maps" in labels, f"{country} missing Google Maps"
            assert "OpenStreetMap" in labels, f"{country} missing OpenStreetMap"

    def test_no_country_has_empty_sources(self) -> None:
        """Every country entry should have at least one source function."""
        for country, sources in SOURCE_REGISTRY.items():
            assert len(sources) > 0, f"{country} has empty sources list"


class TestGetSourcesForCountry:
    """Tests for get_sources_for_country()."""

    def test_returns_default_for_none(self) -> None:
        sources = get_sources_for_country(None)
        assert len(sources) >= 1
        labels = {label for label, _ in sources}
        assert "Google Maps" in labels
        assert "OpenStreetMap" in labels

    def test_returns_default_for_unknown(self) -> None:
        sources = get_sources_for_country("XX")
        assert len(sources) >= 1
        labels = {label for label, _ in sources}
        assert "Google Maps" in labels

    def test_returns_pk_sources(self) -> None:
        sources = get_sources_for_country("PK")
        assert len(sources) == 9
        labels = {label for label, _ in sources}
        assert "Yellow Pages PK" in labels

    def test_returns_us_sources(self) -> None:
        sources = get_sources_for_country("US")
        assert len(sources) == 5
        labels = {label for label, _ in sources}
        assert "Manta" in labels
        assert "MerchantCircle" in labels
        assert "Yelp" in labels

    def test_returns_gb_sources(self) -> None:
        sources = get_sources_for_country("GB")
        assert len(sources) == 6
        labels = {label for label, _ in sources}
        assert "FreeIndex" in labels
        assert "Bizify" in labels
        assert "Thomson Local" in labels
        assert "Yell UK" in labels

    def test_case_insensitive(self) -> None:
        sources_upper = get_sources_for_country("PK")
        sources_lower = get_sources_for_country("pk")
        assert sources_upper == sources_lower

    def test_sources_are_callable(self) -> None:
        """Each source entry should be a callable async function."""
        sources = get_sources_for_country("US")
        for label, fn in sources:
            assert callable(fn), f"{label} is not callable"
            # Should be an async function (coroutine)
            import asyncio
            assert asyncio.iscoroutinefunction(fn), f"{label} is not async"

    def test_default_has_only_google_and_osm(self) -> None:
        """Default should have exactly 2 sources: Google Maps + OSM."""
        default_sources = SOURCE_REGISTRY["default"]
        assert len(default_sources) == 2
        labels = {label for label, _ in default_sources}
        assert labels == {"Google Maps", "OpenStreetMap"}


class TestGetRegisteredCountries:
    """Tests for get_registered_countries()."""

    def test_returns_sorted_list(self) -> None:
        countries = get_registered_countries()
        assert isinstance(countries, list)
        assert countries == sorted(countries)

    def test_excludes_default(self) -> None:
        countries = get_registered_countries()
        assert "default" not in countries

    def test_includes_known_countries(self) -> None:
        countries = get_registered_countries()
        assert "PK" in countries
        assert "US" in countries
        assert "GB" in countries
        assert "DE" in countries
        assert "FR" in countries
        assert "IN" in countries

    def test_has_expected_count(self) -> None:
        """Should have at least 10 countries registered."""
        countries = get_registered_countries()
        assert len(countries) >= 10


class TestRegisterSource:
    """Tests for register_source() runtime registration."""

    def setup_method(self) -> None:
        """Save original registry state for cleanup."""
        self._original = {
            k: list(v) for k, v in SOURCE_REGISTRY.items()
        }

    def teardown_method(self) -> None:
        """Restore original registry state."""
        SOURCE_REGISTRY.clear()
        SOURCE_REGISTRY.update(self._original)

    @pytest.mark.asyncio
    async def _dummy_source(self, keyword: str, location: str) -> list:
        return []

    def test_register_new_country(self) -> None:
        register_source("JP", "Japan Directory", self._dummy_source)
        sources = get_sources_for_country("JP")
        labels = {label for label, _ in sources}
        assert "Japan Directory" in labels
        # Should also include default sources
        assert "Google Maps" in labels

    def test_register_existing_country(self) -> None:
        register_source("PK", "New PK Source", self._dummy_source)
        sources = get_sources_for_country("PK")
        labels = {label for label, _ in sources}
        assert "New PK Source" in labels
        assert "Yellow Pages PK" in labels  # Original sources preserved

    def test_prepend_new_source(self) -> None:
        register_source("PK", "First Source", self._dummy_source, prepend=True)
        sources = get_sources_for_country("PK")
        # Prepend should insert at beginning
        assert sources[0][0] == "First Source"

    def test_register_appends_by_default(self) -> None:
        register_source("PK", "Last Source", self._dummy_source)
        sources = get_sources_for_country("PK")
        # Append should add at end
        assert sources[-1][0] == "Last Source"

    def test_register_new_country_inherits_default(self) -> None:
        register_source("BR", "Brazil Source", self._dummy_source)
        sources = get_sources_for_country("BR")
        labels = {label for label, _ in sources}
        assert "Google Maps" in labels
        assert "OpenStreetMap" in labels

    def test_register_with_prepend_new_country(self) -> None:
        register_source("AR", "Argentina First", self._dummy_source, prepend=True)
        sources = get_sources_for_country("AR")
        assert sources[0][0] == "Argentina First"
