"""Standard response envelope. Mirrors TS utils/response.ts."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class SuccessEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: Any
    meta: dict[str, Any] | None = None


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int
    limit: int
    total: int
    total_pages: int


class PaginatedEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: list[Any]
    meta: Meta


def success(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"success": True, "data": data}
    if meta is not None:
        out["meta"] = meta
    return out


def paginated(
    data: list[Any],
    total: int,
    page: int,
    limit: int,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": (total + limit - 1) // limit,
    }
    if extra_meta:
        meta.update(extra_meta)
    return {"success": True, "data": data, "meta": meta}
