"""Unit tests for deduplication logic. Ported from tests/unit/dedup.test.ts."""

from dataclasses import dataclass


@dataclass
class BizCandidate:
    name: str
    external_id: str | None = None
    phone: str | None = None


@dataclass
class ExistingRecord:
    id: str
    external_id: str | None
    phone: str | None


def find_duplicate(
    candidate: BizCandidate, existing: list[ExistingRecord]
) -> ExistingRecord | None:
    if candidate.external_id:
        for r in existing:
            if r.external_id == candidate.external_id:
                return r
    if candidate.phone:
        for r in existing:
            if r.phone == candidate.phone:
                return r
    return None


def test_match_by_external_id():
    records = [
        ExistingRecord("1", "ext-123", "+15551234567"),
        ExistingRecord("2", "ext-456", "+15559876543"),
    ]
    result = find_duplicate(BizCandidate("Test", "ext-123", "+15551111111"), records)
    assert result is not None
    assert result.id == "1"


def test_match_by_phone():
    records = [
        ExistingRecord("1", "ext-123", "+15551234567"),
        ExistingRecord("2", "ext-456", "+15559876543"),
    ]
    result = find_duplicate(BizCandidate("Other", None, "+15559876543"), records)
    assert result is not None
    assert result.id == "2"


def test_no_match():
    records = [
        ExistingRecord("1", "ext-123", "+15551234567"),
        ExistingRecord("2", "ext-456", "+15559876543"),
    ]
    result = find_duplicate(BizCandidate("New Biz", None, "+15550000000"), records)
    assert result is None
