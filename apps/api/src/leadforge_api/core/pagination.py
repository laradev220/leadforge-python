"""Pagination helper. Mirrors TS utils/pagination.ts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pagination:
    page: int
    limit: int
    skip: int


def get_pagination(query: dict[str, str]) -> Pagination:
    try:
        page = max(1, int(query.get("page", "1")))
    except (TypeError, ValueError):
        page = 1
    try:
        limit = int(query.get("limit", "50"))
    except (TypeError, ValueError):
        limit = 50
    limit = min(100, max(1, limit))
    return Pagination(page=page, limit=limit, skip=(page - 1) * limit)
