"""Fail-closed checks that keep live identifiers out of the simulator."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class SensitiveInputKind(StrEnum):
    """Identifier classes that are never accepted in a synthetic session."""

    PHONE = "phone"
    RESIDENT_REGISTRATION = "resident_registration"
    ACCOUNT_LIKE = "account_like"


@dataclass(frozen=True, slots=True)
class SensitiveInput:
    """A redacted detection result; it intentionally holds no matched value."""

    source: str
    kind: SensitiveInputKind


_SENSITIVE_PATTERNS: Final[tuple[tuple[SensitiveInputKind, re.Pattern[str]], ...]] = (
    (
        SensitiveInputKind.PHONE,
        re.compile(r"(?<!\d)01[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)"),
    ),
    (
        SensitiveInputKind.RESIDENT_REGISTRATION,
        re.compile(r"(?<!\d)\d{6}[- ]?[1-4]\d{6}(?!\d)"),
    ),
    (
        SensitiveInputKind.ACCOUNT_LIKE,
        re.compile(r"(?<!\d)\d{3,6}[- ]\d{2,6}[- ]\d{3,6}(?!\d)"),
    ),
)


def find_sensitive_input(
    message: str, handoff_marker: str | None
) -> SensitiveInput | None:
    """Return a redacted signal when a live-looking identifier is supplied."""
    values = (("message", message), ("handoff_marker", handoff_marker))
    for source, value in values:
        if value is None:
            continue
        for kind, pattern in _SENSITIVE_PATTERNS:
            if pattern.search(value) is not None:
                return SensitiveInput(source=source, kind=kind)
    return None
