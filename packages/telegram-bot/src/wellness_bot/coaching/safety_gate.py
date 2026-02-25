"""Deterministic multilingual crisis detector.

Runs BEFORE any LLM call as step 1 of the coaching pipeline.
Uses compiled regex patterns to detect crisis signals in Russian,
English, and Spanish text. No network calls, no LLM — pure regex.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SafetyGateResult:
    """Result of a safety gate check."""

    risk_level: str  # safe, medium, high, crisis
    safety_action: str  # pass, crisis_protocol, flag_review
    signals: list[str] = field(default_factory=list)
    detector: str = "keyword_regex"


# Each pattern is (compiled_regex, signal_name, risk_level).
_PATTERNS: list[tuple[re.Pattern[str], str, str]] = []


def _p(pattern: str, signal: str, level: str) -> None:
    """Register a compiled pattern."""
    _PATTERNS.append((re.compile(pattern, re.IGNORECASE), signal, level))


# ── Russian crisis patterns ──────────────────────────────────────────────
_p(r"покончить\s*(с\s*собой|жизнь)", "self_harm_ru", "crisis")
_p(r"суицид", "suicide_ru", "crisis")
_p(r"(хочу|хотел[аи]?)\s*(умереть|сдохнуть|не\s*жить)", "death_wish_ru", "crisis")
_p(r"повеситься|порезать\s*вены|прыгну\s*с", "method_ru", "crisis")
_p(r"(убить|убью)\s*(себя)", "self_harm_direct_ru", "crisis")
_p(r"не\s*вижу\s*смысла\s*(жить|в\s*жизни)", "hopelessness_ru", "high")

# ── English crisis patterns ──────────────────────────────────────────────
_p(r"kill\s*(myself|me)", "self_harm_en", "crisis")
_p(r"(want|going)\s*to\s*(die|end\s*(it|my\s*life))", "death_wish_en", "crisis")
_p(r"suicid(e|al)", "suicide_en", "crisis")
_p(r"(cut|hang|shoot|overdose)\s*(myself|me)", "method_en", "crisis")
_p(r"no\s*reason\s*to\s*live", "hopelessness_en", "high")

# ── Spanish crisis patterns ──────────────────────────────────────────────
_p(r"suicidarm[eE]", "suicide_es", "crisis")
_p(r"quiero\s*morir(me)?", "death_wish_es", "crisis")
_p(r"matarm[eE]", "self_harm_es", "crisis")

# ── Violence patterns ────────────────────────────────────────────────────
_p(r"(убить|убью)\s+(его|её|их|человека|людей)", "violence_ru", "crisis")
_p(
    r"(kill|hurt|harm)\s+(someone|him|her|them|people)\s*(bad|serious)?",
    "violence_en",
    "crisis",
)


class SafetyGate:
    """Deterministic multilingual crisis detector.

    Scans user text against compiled regex patterns for crisis signals
    in Russian, English, and Spanish. Returns a structured result with
    risk level and recommended action.
    """

    def check(self, text: str) -> SafetyGateResult:
        """Check text for crisis signals.

        Args:
            text: User message text to scan.

        Returns:
            SafetyGateResult with risk_level, safety_action, and signals.
        """
        if not text or not text.strip():
            return SafetyGateResult(risk_level="safe", safety_action="pass")

        signals: list[str] = []
        levels: set[str] = set()

        for pattern, signal, level in _PATTERNS:
            if pattern.search(text):
                signals.append(signal)
                levels.add(level)

        if "crisis" in levels:
            return SafetyGateResult(
                risk_level="crisis",
                safety_action="crisis_protocol",
                signals=signals,
            )

        if "high" in levels:
            return SafetyGateResult(
                risk_level="high",
                safety_action="flag_review",
                signals=signals,
            )

        return SafetyGateResult(risk_level="safe", safety_action="pass")
