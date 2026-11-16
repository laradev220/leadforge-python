"""LeadForge verification core: email and phone checks."""

from leadforge_verification.email import build_email_verifier, normalize_email, verify_email
from leadforge_verification.phone import classify_phone
from leadforge_verification.providers import (
    EmailVerifier,
    MxEmailVerifier,
    SmtpEmailVerifier,
    ZeroBounceVerifier,
)
from leadforge_verification.types import VerificationResult

__all__ = [
    "EmailVerifier",
    "MxEmailVerifier",
    "SmtpEmailVerifier",
    "VerificationResult",
    "ZeroBounceVerifier",
    "build_email_verifier",
    "classify_phone",
    "normalize_email",
    "verify_email",
]
