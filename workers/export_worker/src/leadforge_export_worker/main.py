"""Export worker. Mirrors workers/export-worker/src/index.ts."""

import csv
import json
from pathlib import Path

from leadforge_config import get_settings
from leadforge_database import get_session_ctx
from leadforge_database.models import (
    Business,
    Export,
    LeadScore,
)
from leadforge_shared.types import ExportJobData
from leadforge_worker_core.core import WorkerWrapper
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def export_processor(data: ExportJobData, logger):
    export_id = data.export_id
    logger.info("processing_export", exportId=str(export_id))

    async with get_session_ctx() as session:
        res_exp = await session.execute(select(Export).where(Export.id == export_id))
        exp = res_exp.scalar_one_or_none()
        if not exp:
            logger.error("export_not_found", exportId=str(export_id))
            raise ValueError("Export not found")

        # Fetch qualified leads (those with LeadScore records)
        query = select(Business).join(LeadScore)

        # Apply filters from the export request (if stored)
        # Prefer queue payload filters (data.filters) which are always passed
        # by the current API. Fall back to exp.filters for backward compatibility
        # with queued jobs created before the filters column was added.
        from sqlalchemy import and_

        filters = data.filters
        where_clauses = []
        if filters:
            if filters.get("score_min") is not None:
                where_clauses.append(LeadScore.score >= int(filters["score_min"]))
            if filters.get("score_max") is not None:
                where_clauses.append(LeadScore.score <= int(filters["score_max"]))
            if filters.get("grade"):
                where_clauses.append(LeadScore.grade == filters["grade"])
            if filters.get("website_status"):
                from leadforge_database.models import WebsiteStatus

                where_clauses.append(
                    Business.website_status == WebsiteStatus(filters["website_status"])
                )
            if filters.get("city"):
                where_clauses.append(Business.city.ilike(f"%{filters['city']}%"))
            if filters.get("country"):
                where_clauses.append(Business.country == filters["country"])
            if filters.get("best_contact_method"):
                where_clauses.append(
                    LeadScore.best_contact_method == filters["best_contact_method"]
                )

        if where_clauses:
            query = query.where(and_(*where_clauses))

        result = await session.execute(
            query.options(
                selectinload(Business.lead_score),
                selectinload(Business.website),
                selectinload(Business.contacts),
                selectinload(Business.social_profiles),
            ).order_by(Business.created_at.desc())
        )
        businesses = result.scalars().all()

        rows = []
        for b in businesses:
            rows.append(
                {
                    "id": str(b.id),
                    "name": b.name,
                    "category": b.category or "",
                    "city": b.city or "",
                    "country": b.country or "",
                    "phone": b.phone or "",
                    "rating": b.rating or "",
                    "review_count": b.review_count or 0,
                    "website_status": b.website_status.value,
                    "website_url": b.website.url if b.website else "",
                    "lead_score": b.lead_score.score if b.lead_score else 0,
                    "grade": b.lead_score.grade if b.lead_score else "",
                    "best_contact": b.lead_score.best_contact_method if b.lead_score else "",
                    "contacts": "; ".join([f"{c.type.value}:{c.value}" for c in b.contacts]),
                    "socials": "; ".join(
                        [f"{p.platform.value}:{p.profile_url}" for p in b.social_profiles]
                    ),
                }
            )

        settings = get_settings()
        export_dir = Path(settings.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"{export_id}.{exp.format.value.lower()}"
        file_path = export_dir / file_name

        if exp.format.value == "JSON":
            with open(file_path, "w") as f:
                json.dump(rows, f, indent=2)
        elif exp.format.value == "CSV":
            if rows:
                with open(file_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
        else:  # XLSX fallback to TSV
            with open(file_path, "w") as f:
                if rows:
                    f.write("\t".join(rows[0].keys()) + "\n")
                    for r in rows:
                        f.write("\t".join(str(v) for v in r.values()) + "\n")

        # Store just the filename relative to export_dir so resolve_export_path can reconstruct it
        exp.file_path = file_name
        exp.total_records = len(rows)
        exp.status = "COMPLETED"
        await session.commit()
        logger.info("export_completed", exportId=str(export_id), path=str(file_path))


worker = WorkerWrapper("export", export_processor)


# ── Module-level arq function ──────────────────────────────────────────────


async def export(ctx: dict, export_id: str) -> None:
    """Arq entry point."""
    data = ExportJobData(export_id=export_id)
    await worker(ctx, data)


def main():
    """Entrypoint — arq 0.28's Worker.run() is synchronous."""
    import time

    from arq import Worker
    from arq.connections import RedisSettings

    settings = get_settings()
    while True:
        try:
            worker_instance = Worker(
                functions=[export],
                queue_name="export",
                redis_settings=RedisSettings(host=settings.redis_host, port=settings.redis_port, password=settings.redis_password or None),
                max_jobs=settings.scraper_concurrency,
            )
            worker_instance.run()
        except Exception as e:
            print(f"[export] worker crashed: {e}, restarting in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    main()
