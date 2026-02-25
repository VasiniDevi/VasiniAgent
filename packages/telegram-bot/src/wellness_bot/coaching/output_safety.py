"""Deterministic post-generation output safety check.

Runs AFTER the LLM generates a response (step 8 in the coaching pipeline).
Scans bot output for diagnosis language, medication advice, and pressure
patterns that a wellness coach must never produce. Pure regex — no network
calls, no LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SafetyCheckResult:
    """Result of an output safety check."""

    approved: bool
    reason: str = ""
    action: str = "pass"  # pass, rewrite, block


# ── Pattern registry ────────────────────────────────────────────────────
# Each entry: (compiled_regex, reason, action)
_PATTERNS: list[tuple[re.Pattern[str], str, str]] = []


def _p(pattern: str, reason: str, action: str) -> None:
    """Register a compiled pattern."""
    _PATTERNS.append((re.compile(pattern, re.IGNORECASE), reason, action))


# ── Diagnosis patterns (reason="diagnosis", action="rewrite") ───────────
_p(
    r"(у\s*вас|у\s*тебя)\s*(депресси[яи]|тревожное\s*расстройство|птср|обсесси|биполярн)",
    "diagnosis",
    "rewrite",
)
_p(r"(ваш|твой)\s*диагноз", "diagnosis", "rewrite")
_p(
    r"you\s*(have|suffer\s*from)\s*(depression|anxiety\s*disorder|ptsd|ocd|bipolar)",
    "diagnosis",
    "rewrite",
)
_p(
    r"(clinical|diagnosed\s*with)\s*(depression|anxiety|disorder)",
    "diagnosis",
    "rewrite",
)

# ── Medication patterns (reason="medication", action="rewrite") ─────────
_p(
    r"(антидепрессант|транквилизатор|нейролептик|снотворн|седативн)",
    "medication",
    "rewrite",
)
_p(
    r"(принять|принимать|назначить|выпить)\s*(таблетк|лекарств|препарат)",
    "medication",
    "rewrite",
)
_p(
    r"(antidepressant|tranquilizer|benzodiazepine|ssri|medication|prescri)",
    "medication",
    "rewrite",
)
_p(r"(take|try)\s*(pills|medication|drugs)", "medication", "rewrite")
_p(r"need\s*medication", "medication", "rewrite")

# ── Pressure patterns (reason="pressure", action="rewrite") ────────────
_p(
    r"(обязан|должен|немедленно|прямо\s*сейчас)\s*(сделай|выполни|начни)",
    "pressure",
    "rewrite",
)
_p(
    r"you\s*(must|have\s*to|need\s*to)\s*(do\s*this|start|immediately)",
    "pressure",
    "rewrite",
)


class OutputSafetyCheck:
    """Deterministic post-generation safety check.

    Validates LLM-generated text against compiled regex patterns to
    ensure the bot never outputs diagnosis, medication advice, or
    pressure language. First matching pattern wins.
    """

    def validate(self, text: str) -> SafetyCheckResult:
        """Check generated text for unsafe patterns.

        Args:
            text: LLM-generated response text to scan.

        Returns:
            SafetyCheckResult indicating whether the text is approved.
        """
        if not text or not text.strip():
            return SafetyCheckResult(approved=True)

        for pattern, reason, action in _PATTERNS:
            if pattern.search(text):
                return SafetyCheckResult(
                    approved=False,
                    reason=reason,
                    action=action,
                )

        return SafetyCheckResult(approved=True)
