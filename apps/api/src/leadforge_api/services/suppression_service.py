"""Workspace-scoped do-not-contact entries."""

from __future__ import annotations

from uuid import UUID

from leadforge_database.models import Suppression
from leadforge_shared.types import SuppressionKind
from leadforge_shared.utils import normalize_phone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.errors import conflict, not_found


def normalize_value(kind: SuppressionKind, value: str) -> str:
    text = value.strip()
    if kind == SuppressionKind.EMAIL:
        return text.lower()
    if kind == SuppressionKind.DOMAIN:
        domain = text.lower().removeprefix("http://").removeprefix("https://")
        domain = domain.split("/", 1)[0]
        return domain.removeprefix("www.")
    return normalize_phone(text)


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Suppression]:
    result = await session.execute(
        select(Suppression)
        .where(Suppression.user_id == user_id)
        .order_by(Suppression.created_at.desc())
    )
    return list(result.scalars())


async def add(
    session: AsyncSession,
    user_id: UUID,
    kind: SuppressionKind,
    value: str,
    reason: str = "manual",
    note: str | None = None,
) -> Suppression:
    entry = Suppression(
        user_id=user_id,
        kind=kind,
        value=normalize_value(kind, value),
        reason=reason,
        note=note,
    )
    session.add(entry)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise conflict("Value is already suppressed") from exc
    await session.refresh(entry)
    return entry


async def remove(session: AsyncSession, user_id: UUID, suppression_id: UUID) -> None:
    result = await session.execute(
        select(Suppression).where(Suppression.id == suppression_id, Suppression.user_id == user_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise not_found("Suppression not found")
    await session.delete(entry)
    await session.commit()


async def matching_values(
    session: AsyncSession, user_id: UUID
) -> tuple[set[str], set[str], set[str]]:
    """Return (emails, phones, domains) to exclude from an export."""
    rows = await list_for_user(session, user_id)
    emails = {row.value for row in rows if row.kind == SuppressionKind.EMAIL}
    phones = {row.value for row in rows if row.kind == SuppressionKind.PHONE}
    domains = {row.value for row in rows if row.kind == SuppressionKind.DOMAIN}
    return emails, phones, domains


async def bulk_add(session: AsyncSession, user_id: UUID, entries: list[dict]) -> tuple[int, int]:
    """Insert many entries idempotently. Returns (added, skipped_duplicates)."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    if not entries:
        return 0, 0
    values = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        kind = SuppressionKind(entry["kind"])
        value = normalize_value(kind, entry["value"])
        key = (kind.value, value)
        if key in seen:
            continue
        seen.add(key)
        values.append(
            {
                "user_id": user_id,
                "kind": kind,
                "value": value,
                "reason": entry.get("reason", "manual"),
                "note": entry.get("note"),
            }
        )
    if not values:
        return 0, len(entries)

    statement = (
        pg_insert(Suppression)
        .values(values)
        .on_conflict_do_nothing(constraint="uq_suppressions_user_kind_value")
        .returning(Suppression.id)
    )
    added = len(list((await session.execute(statement)).scalars()))
    await session.commit()
    return added, len(entries) - added
