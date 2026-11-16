"""API contract tests.

These guard the boundaries that previously failed silently:
- export filter names (``min_score`` vs ``score_min``)
- the export worker accepting the ``filters`` kwarg
- pagination meta key naming
- authentication on every data route
"""

from __future__ import annotations

import inspect
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from leadforge_api.core.errors import AppError
from leadforge_api.core.ratelimit import enforce_rate_limit
from leadforge_api.core.response import paginated
from leadforge_api.main import app
from leadforge_api.schemas import (
    BulkVerifyRequest,
    CreateExportRequest,
    SuppressionBulkRequest,
    SuppressionCreateRequest,
)
from leadforge_export_worker.main import export as export_job
from leadforge_shared.types import ExportFilters, ExportJobData
from pydantic import ValidationError
from starlette.requests import Request

PROTECTED_ROUTES = (
    "/api/v1/leads",
    "/api/v1/businesses",
    "/api/v1/social-profiles",
    "/api/v1/analytics/dashboard",
    "/api/v1/analytics/lead-distribution",
    "/api/v1/exports",
    f"/api/v1/businesses/{uuid.uuid4()}/provenance",
    "/api/v1/suppressions",
    "/api/v1/jobs/activity",
    "/api/v1/verification/capabilities",
)


class TestExportFilters:
    def test_accepts_canonical_names(self) -> None:
        filters = ExportFilters(score_min=10, score_max=90, grade="A", country="GB")
        assert filters.score_min == 10
        assert filters.score_max == 90

    def test_rejects_legacy_min_score(self) -> None:
        with pytest.raises(ValidationError):
            ExportFilters.model_validate({"min_score": 10})

    def test_rejects_inverted_range(self) -> None:
        with pytest.raises(ValidationError):
            ExportFilters(score_min=90, score_max=10)

    def test_rejects_out_of_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ExportFilters(score_min=-1)
        with pytest.raises(ValidationError):
            ExportFilters(score_max=101)

    def test_request_schema_rejects_unknown_filter_keys(self) -> None:
        with pytest.raises(ValidationError):
            CreateExportRequest.model_validate({"format": "CSV", "filters": {"min_score": 5}})


class TestExportJobContract:
    def test_handler_accepts_filters_kwarg(self) -> None:
        """Regression: filtered exports used to crash with TypeError."""
        parameters = inspect.signature(export_job).parameters
        assert "filters" in parameters

    def test_handler_signature_matches_enqueue_payload(self) -> None:
        parameters = set(inspect.signature(export_job).parameters)
        assert {"ctx", "export_id", "filters"} <= parameters

    def test_job_payload_deserializes_queue_filters(self) -> None:
        """arq passes plain JSON; ExportJobData must coerce it."""
        export_id = uuid.uuid4()
        payload = ExportJobData.model_validate(
            {
                "export_id": str(export_id),
                "filters": {"score_min": 10, "score_max": 90, "grade": "A"},
            }
        )
        assert payload.export_id == export_id
        assert payload.filters is not None
        assert payload.filters.score_min == 10
        assert payload.filters.grade.value == "A"


class TestBulkVerifySchema:
    def test_limit_is_capped(self) -> None:
        with pytest.raises(ValidationError):
            BulkVerifyRequest(limit=501)

    def test_defaults(self) -> None:
        body = BulkVerifyRequest()
        assert body.limit == 500
        assert body.force is False
        assert body.verified_email is False
        assert body.business_ids is None

    def test_business_ids_are_capped(self) -> None:
        with pytest.raises(ValidationError):
            BulkVerifyRequest(business_ids=[uuid.uuid4() for _ in range(501)])

    def test_suppression_bulk_shape(self) -> None:
        body = SuppressionBulkRequest(
            entries=[SuppressionCreateRequest(kind="EMAIL", value="a@b.com")]
        )
        assert len(body.entries) == 1
        with pytest.raises(ValidationError):
            SuppressionBulkRequest(entries=[])


class TestPaginationContract:
    def test_meta_uses_snake_case_total_pages(self) -> None:
        body = paginated([], total=120, page=1, limit=50)
        assert body["meta"]["total_pages"] == 3
        assert "totalPages" not in body["meta"]


class TestRouteAuth:
    @pytest.mark.parametrize("path", PROTECTED_ROUTES)
    async def test_rejects_missing_token(self, path: str) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(path)
        assert response.status_code == 401, path


class _FakeRedis:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self._calls = 0

    async def incr(self, _key: str) -> int:
        if self._fail:
            raise ConnectionError("redis down")
        self._calls += 1
        return self._calls

    async def expire(self, _key: str, _ttl: int) -> bool:
        return True

    async def aclose(self) -> None:
        return None


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "headers": [],
            "client": ("1.2.3.4", 1),
        }
    )


class TestVerifyRouteAuth:
    async def test_verify_requires_token(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/businesses/{uuid.uuid4()}/verify")
        assert response.status_code == 401


class TestRateLimit:
    async def test_allows_up_to_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakeRedis()
        monkeypatch.setattr("leadforge_api.core.ratelimit.get_redis_client", lambda: fake)
        await enforce_rate_limit(_request(), bucket="t", limit=2, window_seconds=60)
        await enforce_rate_limit(_request(), bucket="t", limit=2, window_seconds=60)
        with pytest.raises(AppError) as exc:
            await enforce_rate_limit(_request(), bucket="t", limit=2, window_seconds=60)
        assert exc.value.status_code == 429

    async def test_fails_open_when_redis_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "leadforge_api.core.ratelimit.get_redis_client",
            lambda: _FakeRedis(fail=True),
        )
        await enforce_rate_limit(_request(), bucket="t", limit=1, window_seconds=60)
