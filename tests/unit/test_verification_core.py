"""Verification core: MX email checks and phone line typing."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from leadforge_shared.types import PhoneLineType, VerificationStatus
from leadforge_verification import classify_phone, verify_email
from leadforge_verification.providers import MxEmailVerifier


def _lookup(answer: bool | None) -> Callable[[str, int], Awaitable[bool | None]]:
    async def _inner(_domain: str, _timeout: int) -> bool | None:
        return answer

    return _inner


class TestMxVerification:
    async def test_mx_present_is_risky(self) -> None:
        verifier = MxEmailVerifier(lookup=_lookup(True))
        outcome = await verify_email("info@clinic.pk", verifier)
        assert outcome.status == VerificationStatus.RISKY
        assert outcome.confidence == 60
        assert outcome.reason == "mx_present"
        assert outcome.method == "mx"

    async def test_mx_missing_is_invalid(self) -> None:
        verifier = MxEmailVerifier(lookup=_lookup(False))
        outcome = await verify_email("info@dead-domain.test", verifier)
        assert outcome.status == VerificationStatus.INVALID
        assert outcome.reason == "mx_missing"

    async def test_dns_failure_is_unknown(self) -> None:
        verifier = MxEmailVerifier(lookup=_lookup(None))
        outcome = await verify_email("info@flaky.test", verifier)
        assert outcome.status == VerificationStatus.UNKNOWN
        assert outcome.reason == "dns_error"

    async def test_invalid_syntax_skips_lookup(self) -> None:
        calls: list[str] = []

        async def lookup(domain: str, _timeout: int) -> bool:
            calls.append(domain)
            return True

        verifier = MxEmailVerifier(lookup=lookup)
        outcome = await verify_email("not-an-email", verifier)
        assert outcome.status == VerificationStatus.INVALID
        assert outcome.method == "syntax"
        assert calls == []

    async def test_domain_is_normalized_and_cached(self) -> None:
        calls: list[str] = []

        async def lookup(domain: str, _timeout: int) -> bool:
            calls.append(domain)
            return True

        verifier = MxEmailVerifier(lookup=lookup)
        await verifier.verify("Info@Clinic.PK")
        await verifier.verify("sales@clinic.pk")
        assert calls == ["clinic.pk"]

    async def test_never_returns_valid(self) -> None:
        verifier = MxEmailVerifier(lookup=_lookup(True))
        outcome = await verify_email("info@clinic.pk", verifier)
        assert outcome.status != VerificationStatus.VALID


class TestPhoneClassification:
    def test_pakistan_mobile_national(self) -> None:
        line_type, normalized = classify_phone("0332 9307688", "PK")
        assert line_type == PhoneLineType.MOBILE
        assert normalized == "+923329307688"

    def test_pakistan_landline(self) -> None:
        line_type, normalized = classify_phone("+92 91 5613730", "PK")
        assert line_type == PhoneLineType.LANDLINE
        assert normalized == "+92915613730"

    def test_e164_mobile(self) -> None:
        line_type, normalized = classify_phone("+923139252147")
        assert line_type == PhoneLineType.MOBILE
        assert normalized == "+923139252147"

    def test_toll_free(self) -> None:
        line_type, normalized = classify_phone("+1 800 555 0199")
        assert line_type == PhoneLineType.TOLL_FREE
        assert normalized == "+18005550199"

    def test_garbage_is_unknown(self) -> None:
        line_type, normalized = classify_phone("not-a-phone")
        assert line_type == PhoneLineType.UNKNOWN
        assert normalized is None

    def test_empty_is_unknown(self) -> None:
        assert classify_phone("") == (PhoneLineType.UNKNOWN, None)
