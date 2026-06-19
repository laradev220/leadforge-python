"""Centralized error types + FastAPI exception handlers. Mirrors TS utils/errors.ts."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.context = context or {}


def not_found(message: str = "Resource not found") -> AppError:
    return AppError(404, "NOT_FOUND", message)


def bad_request(message: str, context: dict[str, Any] | None = None) -> AppError:
    return AppError(400, "BAD_REQUEST", message, context)


def unauthorized(message: str = "Unauthorized") -> AppError:
    return AppError(401, "UNAUTHORIZED", message)


def conflict(message: str) -> AppError:
    return AppError(409, "CONFLICT", message)
