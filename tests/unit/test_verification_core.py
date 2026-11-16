"""Verification core: MX email checks and phone line typing."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import SimpleNamespace

from leadforge_shared.types import PhoneLineType, VerificationStatus
from leadforge_verification import (
    SmtpEmailVerifier,
    ZeroBounceVerifier,
    build_email_verifier,
    classify_phone,
    verify_email,
)
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


class TestSmtpVerifier:
    async def _run(self, code: int | None):
        async def lookup(_domain: str, _timeout: int) -> str | None:
            return "mx.clinic.pk"

        async def probe(_host: str, _timeout: int, _helo: str, _rcpt: str):
            return code

        verifier = SmtpEmailVerifier(host_lookup=lookup, probe=probe)
        return await verifier.verify("info@clinic.pk")

    async def test_250_is_valid(self) -> None:
        outcome = await self._run(250)
        assert outcome.status == VerificationStatus.VALID
        assert outcome.confidence == 90
        assert outcome.reason == "smtp_250"

    async def test_550_is_invalid(self) -> None:
        outcome = await self._run(550)
        assert outcome.status == VerificationStatus.INVALID
        assert outcome.reason == "smtp_550"

    async def test_greylist_is_unknown(self) -> None:
        outcome = await self._run(451)
        assert outcome.status == VerificationStatus.UNKNOWN
        assert outcome.reason == "smtp_451"

    async def test_unreachable_falls_back_to_risky(self) -> None:
        outcome = await self._run(None)
        assert outcome.status == VerificationStatus.RISKY
        assert outcome.reason == "smtp_unreachable"

    async def test_missing_mx_is_invalid(self) -> None:
        async def lookup(_domain: str, _timeout: int) -> str | None:
            return None

        verifier = SmtpEmailVerifier(host_lookup=lookup)
        outcome = await verifier.verify("info@dead.test")
        assert outcome.status == VerificationStatus.INVALID
        assert outcome.reason == "mx_missing"


class TestZeroBounce:
    async def _run(self, payload: dict, key: str = "key"):
        async def http_get(_url: str, _params: dict) -> dict:
            return payload

        verifier = ZeroBounceVerifier(api_key=key, http_get=http_get)
        return await verifier.verify("info@clinic.pk")

    async def test_valid(self) -> None:
        outcome = await self._run({"status": "valid"})
        assert outcome.status == VerificationStatus.VALID
        assert outcome.confidence == 95

    async def test_catch_all(self) -> None:
        outcome = await self._run({"status": "catch-all"})
        assert outcome.status == VerificationStatus.CATCH_ALL

    async def test_invalid(self) -> None:
        outcome = await self._run({"status": "invalid"})
        assert outcome.status == VerificationStatus.INVALID

    async def test_unknown_falls_back(self) -> None:
        outcome = await self._run({"status": "unknown"})
        assert outcome.status == VerificationStatus.UNKNOWN

    async def test_missing_key(self) -> None:
        outcome = await self._run({"status": "valid"}, key="")
        assert outcome.status == VerificationStatus.UNKNOWN
        assert outcome.reason == "provider_missing_key"


class TestProviderSelection:
    def _settings(self, **overrides):
        base = {
            "email_verifier_provider": "mx",
            "verify_timeout_ms": 5000,
            "verify_smtp_helo_domain": "leadforge.dev",
            "zero_bounce_api_key": "",
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_default_is_mx(self) -> None:
        assert isinstance(build_email_verifier(self._settings()), MxEmailVerifier)

    def test_smtp_selected(self) -> None:
        verifier = build_email_verifier(self._settings(email_verifier_provider="smtp"))
        assert isinstance(verifier, SmtpEmailVerifier)

    def test_zerobounce_selected_with_key(self) -> None:
        verifier = build_email_verifier(
            self._settings(email_verifier_provider="zerobounce", zero_bounce_api_key="k")
        )
        assert isinstance(verifier, ZeroBounceVerifier)

    def test_zerobounce_without_key_falls_back_to_mx(self) -> None:
        verifier = build_email_verifier(self._settings(email_verifier_provider="zerobounce"))
        assert isinstance(verifier, MxEmailVerifier)
