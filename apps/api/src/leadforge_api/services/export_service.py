"""Export service. Mirrors apps/api/src/services/export-service.ts."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from leadforge_config import get_settings
from leadforge_database.models import Export, ExportFormat
from leadforge_shared.types import ExportFilters, ExportStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.errors import not_found
from leadforge_api.core.queue import enqueue_export


async def create_export(
    session: AsyncSession,
    user_id: UUID,
    fmt: ExportFormat,
    filters: ExportFilters | None,
) -> Export:
    payload = filters.model_dump(mode="json", exclude_none=True) if filters is not None else None
    exp = Export(
        user_id=user_id,
        format=fmt,
        status=ExportStatus.PENDING.value,
        filters=payload or None,
    )
    session.add(exp)
    await session.commit()
    await session.refresh(exp)
    await enqueue_export(exp.id, filters=payload or None)
    return exp


async def list_exports(session: AsyncSession, user_id: UUID) -> list[Export]:
    result = await session.execute(
        select(Export).where(Export.user_id == user_id).order_by(Export.created_at.desc()).limit(50)
    )
    return list(result.scalars())


async def get_export(session: AsyncSession, user_id: UUID, export_id: UUID) -> Export:
    result = await session.execute(
        select(Export).where(Export.id == export_id, Export.user_id == user_id)
    )
    exp = result.scalar_one_or_none()
    if exp is None:
        raise not_found("Export not found")
    return exp


def resolve_export_path(exp: Export) -> Path:
    """Return absolute path to export file (or where it would be).

    The worker stores the filename (relative to export_dir) in exp.file_path.
    We join it with export_dir and resolve to an absolute path.
    """
    settings = get_settings()
    base = Path(settings.export_dir)
    if exp.file_path:
        return (base / exp.file_path).resolve()
    return (base / f"{exp.id}.{exp.format.value.lower()}").resolve()
