"""Phone classification via the offline phonenumbers library.

No carrier lookup yet: ambiguous FIXED_LINE_OR_MOBILE numbers are reported as
UNKNOWN rather than guessed.
"""

from __future__ import annotations

import phonenumbers
from leadforge_shared.types import PhoneLineType
from phonenumbers import NumberParseException, PhoneNumberFormat, PhoneNumberType


def classify_phone(value: str, region: str | None = None) -> tuple[PhoneLineType, str | None]:
    """Return (line type, E.164 value or None for unusable input)."""
    text = (value or "").strip()
    if not text:
        return PhoneLineType.UNKNOWN, None

    parsed = None
    for candidate_region in ((region,) if region else ()) + (None, "US"):
        try:
            parsed = phonenumbers.parse(text, candidate_region)
            break
        except NumberParseException:
            continue

    if parsed is None:
        return PhoneLineType.UNKNOWN, None

    normalized = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    if not phonenumbers.is_possible_number(parsed):
        return PhoneLineType.UNKNOWN, None

    number_type = phonenumbers.number_type(parsed)
    mapping = {
        PhoneNumberType.MOBILE: PhoneLineType.MOBILE,
        PhoneNumberType.FIXED_LINE: PhoneLineType.LANDLINE,
        PhoneNumberType.TOLL_FREE: PhoneLineType.TOLL_FREE,
        PhoneNumberType.VOIP: PhoneLineType.VOIP,
    }
    return mapping.get(number_type, PhoneLineType.UNKNOWN), normalized
