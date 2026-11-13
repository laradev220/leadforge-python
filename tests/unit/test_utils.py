"""Shared utility regression tests."""

from __future__ import annotations

from leadforge_shared.utils import is_valid_phone, normalize_phone, region_for_url


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


class TestPhoneValidation:
    def test_region_from_cctld(self) -> None:
        assert region_for_url("https://clinic.pk/contact") == "PK"
        assert region_for_url("https://example.co.uk") == "GB"
        assert region_for_url("https://example.com") is None

    def test_national_number_valid_with_region(self) -> None:
        assert is_valid_phone("0332 9307688", "PK")

    def test_css_digit_run_rejected(self) -> None:
        assert not is_valid_phone("10 10 0 0 0 22 12", "PK")
        assert not is_valid_phone("405557407450515", "PK")

    def test_international_number(self) -> None:
        assert is_valid_phone("+92 332 9307688", "PK")
