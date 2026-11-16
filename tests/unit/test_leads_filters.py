"""Lead list filters for verification state."""

from __future__ import annotations

import uuid

from leadforge_api.services.lead_service import lead_where
from leadforge_database.models import Business
from sqlalchemy import select
from sqlalchemy.dialects import postgresql


def _sql(**overrides) -> str:
    kwargs = {
        "score_min": None,
        "score_max": None,
        "grade": None,
        "website_status": None,
        "best_contact_method": None,
        "city": None,
        "country": None,
        "verified_email": False,
        "has_mobile": False,
    }
    kwargs.update(overrides)
    return str(
        select(Business)
        .where(*lead_where(uuid.uuid4(), **kwargs))
        .compile(dialect=postgresql.dialect())
    )


def test_verified_filter_uses_contact_status() -> None:
    sql = _sql(verified_email=True)
    assert "EXISTS" in sql
    assert "verification_status" in sql


def test_mobile_filter_uses_line_type() -> None:
    sql = _sql(has_mobile=True)
    assert "EXISTS" in sql
    assert "line_type" in sql


def test_no_verification_filters_by_default() -> None:
    sql = _sql()
    assert "verification_status" not in sql
    assert "line_type" not in sql
