"""PII Scanner — regex-based detection for common PII types.

Supported: email, phone, SSN, credit card.
MVP uses regex patterns. Production should add NER-based detection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class PIIType(Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"


@dataclass
class PIIMatch:
    pii_type: PIIType
    value: str
    start: int
    end: int


# Patterns: conservative to minimize false positives
_PII_PATTERNS: dict[PIIType, re.Pattern] = {
    PIIType.EMAIL: re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    PIIType.PHONE: re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}"),
    PIIType.SSN: re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    PIIType.CREDIT_CARD: re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}

_REDACT_LABELS: dict[PIIType, str] = {
    PIIType.EMAIL: "[EMAIL]",
    PIIType.PHONE: "[PHONE]",
    PIIType.SSN: "[SSN]",
    PIIType.CREDIT_CARD: "[CREDIT_CARD]",
}


class PIIScanner:
    """Scan text for PII and optionally redact."""

    def __init__(self, extra_patterns: dict[PIIType, re.Pattern] | None = None) -> None:
        self._patterns = dict(_PII_PATTERNS)
        if extra_patterns:
            self._patterns.update(extra_patterns)

    def scan(self, text: str) -> list[PIIMatch]:
        matches = []
        for pii_type, pattern in self._patterns.items():
            for m in pattern.finditer(text):
                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=m.group(),
                    start=m.start(),
                    end=m.end(),
                ))
        return matches

    def redact(self, text: str) -> str:
        """Replace all PII with type-specific labels."""
        result = text
        # Process matches in reverse order to preserve positions
        matches = sorted(self.scan(text), key=lambda m: m.start, reverse=True)
        for match in matches:
            label = _REDACT_LABELS.get(match.pii_type, "[REDACTED]")
            result = result[:match.start] + label + result[match.end:]
        return result
