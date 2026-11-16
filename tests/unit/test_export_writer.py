"""Export worker unit tests (writers, query filters, failure status)."""

from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path

from leadforge_export_worker.main import _build_query, _write_csv, _write_json, _write_xlsx
from leadforge_shared.types import ExportFilters
from openpyxl import load_workbook
from sqlalchemy.dialects import postgresql

ROWS = [
    {
        "id": "b1",
        "name": "Acme",
        "category": "Dentist",
        "city": "London",
        "country": "GB",
        "phone": "+442079460958",
        "rating": 4.5,
        "review_count": 12,
        "website_status": "FOUND",
        "website_url": "https://acme.test",
        "lead_score": 88,
        "grade": "B",
        "best_contact": "EMAIL",
        "email_status": "VALID",
        "email_verified_at": "2026-11-16T10:00:00+00:00",
        "phone_type": "MOBILE",
        "contacts": "EMAIL:a@acme.test",
        "socials": "FACEBOOK:https://facebook.com/acme",
    }
]


def _sql(filters: ExportFilters) -> str:
    query = _build_query(uuid.uuid4(), filters)
    return str(query.compile(dialect=postgresql.dialect()))


class TestExportWriters:
    def test_csv_has_header_and_rows(self, tmp_path: Path) -> None:
        path = tmp_path / "out.csv"
        _write_csv(path, ROWS)
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["name"] == "Acme"

    def test_csv_empty_still_has_header(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        _write_csv(path, [])
        assert path.read_text().strip() == (
            "id,name,category,city,country,phone,rating,review_count,website_status,"
            "website_url,lead_score,grade,best_contact,email_status,"
            "email_verified_at,phone_type,contacts,socials"
        )

    def test_json_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "out.json"
        _write_json(path, ROWS)
        assert json.loads(path.read_text())[0]["name"] == "Acme"

    def test_xlsx_is_a_real_workbook(self, tmp_path: Path) -> None:
        path = tmp_path / "out.xlsx"
        _write_xlsx(path, ROWS)
        # Would raise BadZipFile if we were still writing TSV bytes.
        workbook = load_workbook(path)
        sheet = workbook["leads"]
        assert sheet.cell(row=1, column=1).value == "id"
        assert sheet.cell(row=2, column=2).value == "Acme"


class TestExportQuery:
    def test_scoped_to_user(self) -> None:
        sql = _sql(ExportFilters(verified_email_only=False))
        assert "search_jobs.user_id" in sql

    def test_verified_filter_defaults_on(self) -> None:
        sql = _sql(ExportFilters())
        assert "verification_status" in sql

    def test_verified_filter_can_be_disabled(self) -> None:
        sql = _sql(ExportFilters(verified_email_only=False))
        assert "verification_status" not in sql

    def test_score_filters_applied(self) -> None:
        sql = _sql(ExportFilters(score_min=30, score_max=80))
        assert "lead_scores.score >=" in sql
        assert "lead_scores.score <=" in sql

    def test_search_job_filter_applied(self) -> None:
        job_id = uuid.uuid4()
        sql = _sql(ExportFilters(search_job_id=job_id))
        assert "search_job_businesses.search_job_id" in sql

    def test_city_and_grade_applied(self) -> None:
        sql = _sql(ExportFilters(city="London", grade="A"))
        assert "businesses.city ILIKE" in sql
        assert "lead_scores.grade" in sql


class TestSuppressionRows:
    def _business(self):
        from types import SimpleNamespace

        from leadforge_shared.types import (
            ContactType,
            PhoneLineType,
            VerificationStatus,
            WebsiteStatus,
        )

        contact = SimpleNamespace(
            type=ContactType.EMAIL,
            value="info@clinic.pk",
            verification_status=VerificationStatus.RISKY,
            verified_at=None,
            line_type=None,
        )
        phone = SimpleNamespace(
            type=ContactType.PHONE,
            value="+923329307688",
            verification_status=VerificationStatus.VALID,
            verified_at=None,
            line_type=PhoneLineType.MOBILE,
        )
        return SimpleNamespace(
            id="b1",
            name="Clinic",
            category="Dentist",
            city="Peshawar",
            country="PK",
            phone="+923329307688",
            rating=4.5,
            review_count=3,
            website_status=WebsiteStatus.FOUND,
            website=None,
            lead_score=SimpleNamespace(score=70, grade="C", best_contact_method="EMAIL"),
            contacts=[contact, phone],
            social_profiles=[],
        )

    def test_verification_columns_populated(self) -> None:
        from leadforge_export_worker.main import _build_rows

        row = _build_rows([self._business()])[0]
        assert row["email_status"] == "RISKY"
        assert row["phone_type"] == "MOBILE"

    def test_suppressed_email_skips_business(self) -> None:
        from leadforge_export_worker.main import _build_rows

        rows = _build_rows([self._business()], ({"info@clinic.pk"}, set(), set()))
        assert rows == []

    def test_suppressed_domain_skips_business(self) -> None:
        from leadforge_export_worker.main import _build_rows

        rows = _build_rows([self._business()], (set(), set(), {"clinic.pk"}))
        assert rows == []

    def test_suppressed_phone_skips_business(self) -> None:
        from leadforge_export_worker.main import _build_rows

        rows = _build_rows([self._business()], (set(), {"+923329307688"}, set()))
        assert rows == []
