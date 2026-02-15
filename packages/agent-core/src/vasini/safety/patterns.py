"""Jailbreak detection — pattern-based scanning.

MVP: regex patterns for common jailbreak techniques.
Production: add LLM-based classification as secondary check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ScanResult:
    is_safe: bool
    reason: str = ""
    pattern_matched: str = ""


# Patterns target specific jailbreak techniques, not general conversation
_DEFAULT_JAILBREAK_PATTERNS: list[str] = [
    # Instruction override attempts
    r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
    r"(?i)disregard\s+(?:all\s+)?(?:previous|prior|your)\s+(?:instructions|rules|guidelines)",
    r"(?i)forget\s+(?:all\s+)?(?:your|previous)\s+(?:instructions|rules|training)",
    # Role-play bypass
    r"(?i)you\s+are\s+(?:now\s+)?(?:DAN|STAN|DUDE|Evil)",
    r"(?i)(?:activate|enable|enter)\s+(?:developer|admin|god|sudo)\s+mode",
    r"(?i)jailbreak(?:ed)?",
    # System prompt extraction
    r"(?i)(?:print|show|display|reveal|output)\s+(?:your\s+)?(?:system\s+)?prompt\s+verbatim",
    r"(?i)(?:what|show)\s+(?:is|are)\s+your\s+(?:system|initial)\s+(?:prompt|instructions)",
    # Token manipulation
    r"(?i)\[SYSTEM\]|\[INST\]|<<SYS>>",
]


class JailbreakDetector:
    """Detect jailbreak attempts via regex patterns."""

    def __init__(self, extra_patterns: list[str] | None = None) -> None:
        patterns = list(_DEFAULT_JAILBREAK_PATTERNS)
        if extra_patterns:
            patterns.extend(extra_patterns)
        self._compiled = [re.compile(p) for p in patterns]

    def scan(self, text: str) -> ScanResult:
        for pattern in self._compiled:
            match = pattern.search(text)
            if match:
                return ScanResult(
                    is_safe=False,
                    reason=f"Jailbreak pattern detected: {match.group()[:50]}",
                    pattern_matched=pattern.pattern,
                )
        return ScanResult(is_safe=True)
