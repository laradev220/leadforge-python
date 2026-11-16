"""Email verification entrypoints."""

from __future__ import annotations

from leadforge_config import get_settings
from leadforge_shared.types import VerificationStatus
from leadforge_shared.utils import is_valid_email

from leadforge_verification.providers import EmailVerifier, MxEmailVerifier
from leadforge_verification.types import VerificationResult, result


def normalize_email(value: str) -> str:
    return value.strip().lower()


def build_email_verifier(settings=None) -> EmailVerifier:
    """Build the configured verifier. Slice 2 supports MX only."""
    settings = settings or get_settings()
    # smtp/zerobounce adapters land in the next slice; MX is the safe default.
    return MxEmailVerifier(timeout_ms=settings.verify_timeout_ms)


async def verify_email(value: str, verifier: EmailVerifier) -> VerificationResult:
    normalized = normalize_email(value)
    if not is_valid_email(normalized):
        return result(
            VerificationStatus.INVALID,
            confidence=0,
            reason="invalid_syntax",
            method="syntax",
        )
    return await verifier.verify(normalized)
