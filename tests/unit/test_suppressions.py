"""Suppression normalization."""

from __future__ import annotations

from leadforge_api.services.suppression_service import normalize_value
from leadforge_shared.types import SuppressionKind


def test_email_is_lowercased() -> None:
    assert normalize_value(SuppressionKind.EMAIL, "  Info@Clinic.PK ") == "info@clinic.pk"


def test_domain_strips_scheme_www_and_path() -> None:
    assert normalize_value(SuppressionKind.DOMAIN, "https://www.Clinic.pk/contact") == "clinic.pk"


def test_phone_normalizes_to_e164() -> None:
    assert normalize_value(SuppressionKind.PHONE, "+92 332 9307688") == "+923329307688"
