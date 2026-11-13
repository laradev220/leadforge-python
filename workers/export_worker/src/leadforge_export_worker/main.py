"""Export worker. Mirrors workers/export-worker/src/index.ts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from leadforge_config import get_settings
from leadforge_database import get_session_ctx
from leadforge_database.models import (
    Business,
    Export,
    LeadScore,
    SearchJob,
    SearchJobBusiness,
)
from leadforge_shared.types import ExportFilters, ExportFormat, ExportJobData, ExportStatus
from leadforge_worker_core.core import WorkerWrapper
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

COLUMNS: tuple[str, ...] = (
    "id",
    "name",
    "category",
    "city",
    "country",
    "phone",
    "rating",
    "review_count",
    "website_status",
    "website_url",
    "lead_score",
    "grade",
    "best_contact",
    "contacts",
    "socials",
)


async def _load_filters(exp: Export, data: ExportJobData, logger: Any) -> ExportFilters:
    """Prefer the queue payload, fall back to the filters persisted on the row."""
    if data.filters is not None:
        return data.filters
    if exp.filters:
        try:
            return ExportFilters.model_validate(exp.filters)
        except ValueError:
            logger.warning(
                "invalid_stored_export_filters",
                exportId=str(exp.id),
                filters=exp.filters,
            )
    return ExportFilters()


def _build_query(user_id: UUID, filters: ExportFilters):
    """Leads visible to ``user_id``, optionally narrowed by export filters.

    A business is visible when it was discovered by one of the user's search
    jobs. Without this join every export leaks all tenants' data.
    """
    query = (
        select(Business)
        .join(LeadScore, LeadScore.business_id == Business.id)
        .join(SearchJobBusiness, SearchJobBusiness.business_id == Business.id)
        .join(SearchJob, SearchJob.id == SearchJobBusiness.search_job_id)
        .where(SearchJob.user_id == user_id)
        .distinct()
    )

    if filters.search_job_id is not None:
        query = query.where(SearchJobBusiness.search_job_id == filters.search_job_id)
    if filters.score_min is not None:
        query = query.where(LeadScore.score >= filters.score_min)
    if filters.score_max is not None:
        query = query.where(LeadScore.score <= filters.score_max)
    if filters.grade:
        query = query.where(LeadScore.grade == filters.grade.value)
    if filters.website_status:
        query = query.where(Business.website_status == filters.website_status)
    if filters.city:
        query = query.where(Business.city.ilike(f"%{filters.city}%"))
    if filters.country:
        query = query.where(Business.country == filters.country)
    if filters.best_contact_method:
        query = query.where(LeadScore.best_contact_method == filters.best_contact_method.value)
    return query


def _build_rows(businesses: list[Business]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for b in businesses:
        rows.append(
            {
                "id": str(b.id),
                "name": b.name,
                "category": b.category or "",
                "city": b.city or "",
                "country": b.country or "",
                "phone": b.phone or "",
                "rating": b.rating if b.rating is not None else "",
                "review_count": b.review_count or 0,
                "website_status": b.website_status.value,
                "website_url": b.website.url if b.website else "",
                "lead_score": b.lead_score.score if b.lead_score else 0,
                "grade": b.lead_score.grade if b.lead_score else "",
                "best_contact": b.lead_score.best_contact_method if b.lead_score else "",
                "contacts": "; ".join(f"{c.type.value}:{c.value}" for c in b.contacts),
                "socials": "; ".join(
                    f"{p.platform.value}:{p.profile_url}" for p in b.social_profiles
                ),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)


def _write_xlsx(path: Path, rows: list[dict[str, Any]]) -> None:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("leads")
    sheet.append(list(COLUMNS))
    for row in rows:
        sheet.append([row[column] for column in COLUMNS])
    workbook.save(path)


_WRITERS = {
    ExportFormat.CSV: _write_csv,
    ExportFormat.JSON: _write_json,
    ExportFormat.XLSX: _write_xlsx,
}


async def _collect_businesses(
    session: AsyncSession, user_id: UUID, filters: ExportFilters
) -> list[Business]:
    result = await session.execute(
        _build_query(user_id, filters)
        .options(
            selectinload(Business.lead_score),
            selectinload(Business.website),
            selectinload(Business.contacts),
            selectinload(Business.social_profiles),
        )
        .order_by(Business.created_at.desc())
    )
    return list(result.scalars().all())


async def export_processor(data: ExportJobData, logger):
    export_id = data.export_id
    logger.info("processing_export", exportId=str(export_id))

    async with get_session_ctx() as session:
        res_exp = await session.execute(select(Export).where(Export.id == export_id))
        exp = res_exp.scalar_one_or_none()
        if not exp:
            logger.error("export_not_found", exportId=str(export_id))
            raise ValueError("Export not found")

        exp.status = ExportStatus.PROCESSING.value
        await session.commit()

        file_path: Path | None = None
        try:
            filters = await _load_filters(exp, data, logger)
            businesses = await _collect_businesses(session, exp.user_id, filters)
            rows = _build_rows(businesses)

            settings = get_settings()
            export_dir = Path(settings.export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)

            fmt = ExportFormat(exp.format)
            file_name = f"{export_id}.{fmt.value.lower()}"
            file_path = export_dir / file_name

            _WRITERS[fmt](file_path, rows)

            exp.file_path = file_name
            exp.total_records = len(rows)
            exp.status = ExportStatus.COMPLETED.value
            if exp.filters is None and data.filters is not None:
                exp.filters = data.filters.model_dump(mode="json", exclude_none=True) or None
            await session.commit()
            logger.info(
                "export_completed",
                exportId=str(export_id),
                path=str(file_path),
                records=len(rows),
            )
        except Exception as exc:
            await session.rollback()
            await _mark_failed(session, export_id)
            if file_path and file_path.exists():
                file_path.unlink(missing_ok=True)
            logger.error("export_failed", exportId=str(export_id), error=str(exc))
            raise


async def _mark_failed(session: AsyncSession, export_id: UUID) -> None:
    """Record FAILED so the UI stops polling forever."""
    try:
        exp = (
            await session.execute(select(Export).where(Export.id == export_id))
        ).scalar_one_or_none()
        if exp is not None:
            exp.status = ExportStatus.FAILED.value
            await session.commit()
    except Exception:
        await session.rollback()


worker: WorkerWrapper[ExportJobData] = WorkerWrapper("export", export_processor)


# ── Module-level arq function ──────────────────────────────────────────────


async def export(ctx: dict, export_id: str, filters: dict[str, Any] | None = None) -> None:
    """Arq entry point. ``filters`` must be accepted or filtered exports crash."""
    data = ExportJobData(
        export_id=UUID(export_id),
        filters=ExportFilters.model_validate(filters) if filters is not None else None,
    )
    await worker(ctx, data)


def main():
    """Entrypoint — arq 0.28's Worker.run() is synchronous."""
    from leadforge_worker_core.core import run_worker

    run_worker("export", export)


if __name__ == "__main__":
    main()
