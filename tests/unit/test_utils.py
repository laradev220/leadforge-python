"""Shared utility regression tests."""

from __future__ import annotations

from leadforge_shared.utils import normalize_phone


class TestNormalizePhone:
    def test_us_national(self) -> None:
        assert normalize_phone("(555) 123-4567") == "+15551234567"

    def test_uk_national_with_region(self) -> None:
        assert normalize_phone("020 7946 0958", "GB") == "+442079460958"

    def test_pakistan_national_with_region(self) -> None:
        assert normalize_phone("03001234567", "PK") == "+923001234567"

    def test_e164_passthrough(self) -> None:
        assert normalize_phone("+92 300 1234567") == "+923001234567"

    def test_international_prefix(self) -> None:
        assert normalize_phone("0044 20 7946 0958") == "+442079460958"

    def test_ambiguous_number_is_not_mis_prefixed(self) -> None:
        """Without a region, a national trunk-zero number must not become +30..."""
        result = normalize_phone("03001234567")
        assert result == "03001234567"
        assert not result.startswith("+3")
