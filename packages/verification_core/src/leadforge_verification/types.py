"""Verification result types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from leadforge_shared.types import VerificationStatus


@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus
    confidence: int
    reason: str | None
    method: str
    checked_at: datetime


def result(
    status: VerificationStatus,
    *,
    confidence: int,
    reason: str | None,
    method: str,
) -> VerificationResult:
    return VerificationResult(
        status=status,
        confidence=confidence,
        reason=reason,
        method=method,
        checked_at=datetime.now(UTC),
    )
