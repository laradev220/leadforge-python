"""Field provenance helpers.

One row per (business, field, value). Re-seeing the same value refreshes
``last_checked_at``/confidence but never ``first_seen_at``; a changed value
creates a new row so history is preserved.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_database.models import FieldProvenance


async def record_provenance(
    session: AsyncSession,
    *,
    business_id: UUID,
    field: str,
    value: str | None,
    source: str,
    source_url: str | None = None,
    confidence: int = 50,
    enrichment_run_id: UUID | None = None,
) -> None:
    if value is None:
        return
    text = str(value).strip()
    if not text:
        return

    statement = pg_insert(FieldProvenance).values(
        business_id=business_id,
        field=field,
        value=text,
        source=source,
        source_url=source_url,
        confidence=confidence,
        first_seen_at=func.now(),
        last_checked_at=func.now(),
        enrichment_run_id=enrichment_run_id,
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_field_provenance_business_field_value",
        set_={
            "source": statement.excluded.source,
            "source_url": statement.excluded.source_url,
            "confidence": statement.excluded.confidence,
            "last_checked_at": func.now(),
            "enrichment_run_id": statement.excluded.enrichment_run_id,
        },
    )
    await session.execute(statement)


async def provenance_for_business(
    session: AsyncSession, business_id: UUID
) -> list[FieldProvenance]:
    result = await session.execute(
        select(FieldProvenance)
        .where(FieldProvenance.business_id == business_id)
        .order_by(FieldProvenance.first_seen_at.desc(), FieldProvenance.field)
    )
    return list(result.scalars())


async def record_many(
    session: AsyncSession,
    *,
    business_id: UUID,
    values: dict[str, object],
    source: str,
    source_url: str | None = None,
    confidence: int = 50,
) -> None:
    for field, value in values.items():
        await record_provenance(
            session,
            business_id=business_id,
            field=field,
            value=None if value is None else str(value),
            source=source,
            source_url=source_url,
            confidence=confidence,
        )
