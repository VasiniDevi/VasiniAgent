"""LLM adapter with contract-bound generation and multi-layer validation."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from wellness_bot.protocol.types import LLMContract, RiskLevel
from wellness_bot.protocol.style_validator import (
    CheckResult,
    StyleValidationInput,
    validate_style,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Voice + style system prompt (embedded as constant)
# ---------------------------------------------------------------------------

STYLE_SYSTEM_PROMPT = """\
[VOICE + STYLE LAYER]

You are a warm, human wellness coach (CBT/MCT-oriented), not a clinical
authority.
Your tone is natural, direct, and supportive. You speak like a real person, not
a manual.

Core behavior each turn:
1) Acknowledge emotion/context briefly.
2) Give one clear, practical next step.
3) End with one interactive CTA (short question or button prompt).

Default response shape:
- 1-3 short sentences
- max 1 question
- plain language, no jargon unless user asks
- actionable, concrete

Proactivity:
- Do not wait passively.
- If user is stuck/confused, immediately simplify the step.
- If user goes silent, send a short gentle nudge (per timeout policy).
- After completion, reinforce briefly and move forward.

Humor and sarcasm policy:
- Allowed: light, playful, micro-humor (one short line max).
- Goal: warmth and relatability, never ridicule.
- Only when risk_level=SAFE and user tone is receptive/playful.
- Forbidden in CAUTION/CRISIS, shame, grief, trauma, self-harm, hopelessness
spikes.
- If user reacts negatively, switch immediately to warm-neutral tone.

Directness:
- Be straightforward and clear.
- No vague advice, no long disclaimers in normal flow.
- One step at a time.

Long-form mode:
- Default is concise.
- Longer responses are allowed only when needed:
  - user asks for depth,
  - complex emotional story,
  - formulation/reflection requires synthesis.
- In long-form, stay structured and grounded, then return to short interactive
mode.

Never do:
- Diagnose mental disorders.
- Give medication instructions.
- Claim to replace therapy.
- Provide self-harm instructions.
- Minimize risk signals.

Safety override:
- If safety policy requires escalation, follow safety protocol exactly.
- In CRISIS imminent: no playful tone, no sarcasm, no style experimentation.
- Safety instructions override all style rules.

RU-focused variant (if locale is ru):

\u0413\u043e\u0432\u043e\u0440\u0438 \u043f\u043e-\u0447\u0435\u043b\u043e\u0432\u0435\u0447\u0435\u0441\u043a\u0438: \u0442\u0435\u043f\u043b\u043e, \u044f\u0441\u043d\u043e, \u0431\u0435\u0437 \u043a\u0430\u043d\u0446\u0435\u043b\u044f\u0440\u0438\u0442\u0430.
\u041a\u043e\u0440\u043e\u0442\u043a\u043e: 1-3 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u044f, 1 \u0432\u043e\u043f\u0440\u043e\u0441 \u043c\u0430\u043a\u0441\u0438\u043c\u0443\u043c.
\u0424\u043e\u0440\u043c\u0430\u0442 \u043a\u0430\u0436\u0434\u043e\u0433\u043e \u043e\u0442\u0432\u0435\u0442\u0430: \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430 \u2192 \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u044b\u0439 \u0448\u0430\u0433 \u2192 \u0438\u043d\u0442\u0435\u0440\u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0439 \u0432\u043e\u043f\u0440\u043e\u0441.

\u041c\u043e\u0436\u043d\u043e \u043b\u0451\u0433\u043a\u0438\u0439 \u044e\u043c\u043e\u0440/\u043c\u0438\u043a\u0440\u043e-\u0441\u0430\u0440\u043a\u0430\u0437\u043c (1 \u043a\u043e\u0440\u043e\u0442\u043a\u0430\u044f \u0444\u0440\u0430\u0437\u0430), \u0442\u043e\u043b\u044c\u043a\u043e \u0435\u0441\u043b\u0438 SAFE \u0438
\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u0432 \u0442\u0430\u043a\u043e\u043c \u0442\u043e\u043d\u0435.
\u041d\u0435\u043b\u044c\u0437\u044f \u044e\u043c\u043e\u0440/\u0441\u0430\u0440\u043a\u0430\u0437\u043c \u043f\u0440\u0438 \u0440\u0438\u0441\u043a\u0435, \u0441\u0442\u044b\u0434\u0435, \u0433\u043e\u0440\u0435, \u0442\u0440\u0430\u0432\u043c\u0435, \u0441\u0430\u043c\u043e\u043f\u043e\u0432\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u0438.

\u0411\u0443\u0434\u044c \u043f\u0440\u043e\u0430\u043a\u0442\u0438\u0432\u043d\u044b\u043c:
- \u0435\u0441\u043b\u0438 \u0441\u043b\u043e\u0436\u043d\u043e \u2014 \u0443\u043f\u0440\u043e\u0441\u0442\u0438 \u0448\u0430\u0433;
- \u0435\u0441\u043b\u0438 \u0442\u0438\u0448\u0438\u043d\u0430 \u2014 \u043c\u044f\u0433\u043a\u0438\u0439 \u043f\u0438\u043d\u0433;
- \u0435\u0441\u043b\u0438 \u043f\u0440\u043e\u0433\u0440\u0435\u0441\u0441 \u2014 \u043a\u043e\u0440\u043e\u0442\u043a\u043e \u043f\u043e\u0434\u043a\u0440\u0435\u043f\u0438 \u0438 \u0432\u0435\u0434\u0438 \u0434\u0430\u043b\u044c\u0448\u0435.

\u041d\u0438\u043a\u043e\u0433\u0434\u0430: \u0434\u0438\u0430\u0433\u043d\u043e\u0437\u044b, \u0441\u043e\u0432\u0435\u0442\u044b \u043f\u043e \u043b\u0435\u043a\u0430\u0440\u0441\u0442\u0432\u0430\u043c, \u043e\u0431\u0435\u0449\u0430\u043d\u0438\u044f \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0430, \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438 \u043f\u043e
\u0441\u0430\u043c\u043e\u043f\u043e\u0432\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u044e.
\u041f\u0440\u0438 \u0440\u0438\u0441\u043a\u0435 \u0431\u0435\u0437\u043e\u043f\u0430\u0441\u043d\u043e\u0441\u0442\u044c \u0432\u0430\u0436\u043d\u0435\u0435 \u0441\u0442\u0438\u043b\u044f.
"""

# ---------------------------------------------------------------------------
# State-specific fallback templates
# ---------------------------------------------------------------------------

STATE_FALLBACKS: dict[str, str] = {
    "SAFETY_CHECK": "\u042f \u0440\u044f\u0434\u043e\u043c. \u0415\u0441\u043b\u0438 \u0432\u0430\u043c \u0441\u0435\u0439\u0447\u0430\u0441 \u0442\u044f\u0436\u0435\u043b\u043e, \u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430, \u043e\u0431\u0440\u0430\u0442\u0438\u0442\u0435\u0441\u044c \u043d\u0430 \u043b\u0438\u043d\u0438\u044e \u043f\u043e\u043c\u043e\u0449\u0438: 8-800-2000-122.",
    "ESCALATION": "\u041f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430, \u043e\u0431\u0440\u0430\u0442\u0438\u0442\u0435\u0441\u044c \u043d\u0430 \u043b\u0438\u043d\u0438\u044e \u043f\u043e\u043c\u043e\u0449\u0438: 8-800-2000-122. \u042d\u0442\u043e \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e \u0438 \u0430\u043d\u043e\u043d\u0438\u043c\u043d\u043e.",
    "INTAKE": "\u0414\u0430\u0432\u0430\u0439\u0442\u0435 \u043d\u0430\u0447\u043d\u0451\u043c \u0437\u043d\u0430\u043a\u043e\u043c\u0441\u0442\u0432\u043e. \u041a\u0430\u043a \u0432\u044b \u0441\u0435\u0431\u044f \u0447\u0443\u0432\u0441\u0442\u0432\u0443\u0435\u0442\u0435 \u0441\u0435\u0433\u043e\u0434\u043d\u044f?",
    "FORMULATION": "\u041f\u043e\u043d\u0438\u043c\u0430\u044e, \u0447\u0442\u043e \u0432\u0430\u043c \u043d\u0435\u043f\u0440\u043e\u0441\u0442\u043e. \u0414\u0430\u0432\u0430\u0439\u0442\u0435 \u0440\u0430\u0437\u0431\u0435\u0440\u0451\u043c\u0441\u044f \u0432\u043c\u0435\u0441\u0442\u0435 \u2014 \u0447\u0442\u043e \u0441\u0435\u0439\u0447\u0430\u0441 \u0431\u0435\u0441\u043f\u043e\u043a\u043e\u0438\u0442 \u0431\u043e\u043b\u044c\u0448\u0435 \u0432\u0441\u0435\u0433\u043e?",
    "GOAL_SETTING": "\u0414\u0430\u0432\u0430\u0439\u0442\u0435 \u0432\u044b\u0431\u0435\u0440\u0435\u043c, \u043d\u0430\u0434 \u0447\u0435\u043c \u043f\u043e\u0440\u0430\u0431\u043e\u0442\u0430\u0435\u043c \u0441\u0435\u0433\u043e\u0434\u043d\u044f. \u0427\u0442\u043e \u0434\u043b\u044f \u0432\u0430\u0441 \u0441\u0435\u0439\u0447\u0430\u0441 \u0432\u0430\u0436\u043d\u0435\u0435 \u0432\u0441\u0435\u0433\u043e?",
    "MODULE_SELECT": "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0443, \u043a\u043e\u0442\u043e\u0440\u0430\u044f \u043f\u043e\u0434\u0445\u043e\u0434\u0438\u0442 \u0432\u0430\u043c \u043f\u0440\u044f\u043c\u043e \u0441\u0435\u0439\u0447\u0430\u0441.",
    "PRACTICE": "\u0414\u0430\u0432\u0430\u0439\u0442\u0435 \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u043c \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0443. \u0413\u043e\u0442\u043e\u0432\u044b \u043a \u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0435\u043c\u0443 \u0448\u0430\u0433\u0443?",
    "REFLECTION": "\u041a\u0430\u043a \u0432\u044b \u0441\u0435\u0431\u044f \u0447\u0443\u0432\u0441\u0442\u0432\u0443\u0435\u0442\u0435 \u043f\u043e\u0441\u043b\u0435 \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0438? \u041e\u0446\u0435\u043d\u0438\u0442\u0435 \u043e\u0442 1 \u0434\u043e 10.",
    "REFLECTION_LITE": "\u041a\u0430\u043a \u043e\u0449\u0443\u0449\u0435\u043d\u0438\u044f \u043f\u043e\u0441\u043b\u0435 \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0438? \u041e\u0446\u0435\u043d\u0438\u0442\u0435 \u043a\u043e\u0440\u043e\u0442\u043a\u043e.",
    "HOMEWORK": "\u041e\u0442\u043b\u0438\u0447\u043d\u043e. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u044c \u044d\u0442\u0443 \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0443 \u0437\u0430\u0432\u0442\u0440\u0430. \u0413\u043e\u0442\u043e\u0432\u044b?",
    "SESSION_END": "\u0421\u043f\u0430\u0441\u0438\u0431\u043e \u0437\u0430 \u0441\u0435\u0441\u0441\u0438\u044e. \u0411\u0435\u0440\u0435\u0433\u0438\u0442\u0435 \u0441\u0435\u0431\u044f, \u0434\u043e \u0432\u0441\u0442\u0440\u0435\u0447\u0438!",
}

DEFAULT_FALLBACK = "\u041f\u043e\u043d\u0438\u043c\u0430\u044e. \u0414\u0430\u0432\u0430\u0439\u0442\u0435 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0435\u043c \u043f\u043e-\u0434\u0440\u0443\u0433\u043e\u043c\u0443. \u0427\u0442\u043e \u0441\u0435\u0439\u0447\u0430\u0441 \u0432\u0430\u0436\u043d\u0435\u0435 \u0432\u0441\u0435\u0433\u043e?"

# ---------------------------------------------------------------------------
# Diagnostic / medication / harmful lexicon patterns
# ---------------------------------------------------------------------------

_DIAGNOSIS_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(у вас|у тебя)\s+(депресси|тревожн|биполяр|шизофрен|птср|окр|bpd|adhd|ocd)",
        r"\byou have\s+(depression|anxiety|bipolar|schizophrenia|ptsd|ocd|bpd|adhd)\b",
        r"\bдиагноз\b",
        r"\bdiagnos(e|is|ed)\b",
    ]
]

_MEDICATION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(прими|принимай|назначаю|рекомендую)\s+(таблетк|препарат|лекарств|антидепрессант)",
        r"\b(дозировк|дозу)\b",
        r"\b(take|prescribe|recommend)\s+(medication|pills|antidepressant|benzodiazepine)\b",
        r"\b(dosage|milligrams|mg)\b",
    ]
]

_SAFETY_LEXICON_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"как\s+(причинить|навредить)\s+себе",
        r"how\s+to\s+(harm|hurt|kill)\s+(yourself|myself)",
        r"способ(ы|ов)?\s+(суицид|самоубийств)",
        r"method(s)?\s+of\s+(suicide|self.harm)",
    ]
]


# ---------------------------------------------------------------------------
# ResponseValidator (9 checks from the contract)
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    passed: bool
    code: str
    reason: str | None = None
    critical: bool = False


class ResponseValidator:
    """Validates LLM output against the contract and safety rules."""

    def validate(self, text: str, contract: LLMContract) -> list[ValidationResult]:
        results: list[ValidationResult] = []

        # 1) length
        results.append(self._check_length(text, contract))
        # 2) must_include
        results.append(self._check_must_include(text, contract))
        # 3) must_not
        results.append(self._check_must_not(text, contract))
        # 4) no_diagnosis
        results.append(self._check_no_diagnosis(text))
        # 5) no_medication
        results.append(self._check_no_medication(text))
        # 6) language_match
        results.append(self._check_language_match(text, contract))
        # 7) state_alignment
        results.append(self._check_state_alignment(text, contract))
        # 8) actionability
        results.append(self._check_actionability(text))
        # 9) safety_lexicon
        results.append(self._check_safety_lexicon(text))

        return results

    # -- individual checks --------------------------------------------------

    def _check_length(self, text: str, contract: LLMContract) -> ValidationResult:
        ok = len(text) <= contract.max_chars_per_message
        return ValidationResult(
            passed=ok,
            code="length",
            reason=f"len={len(text)}, max={contract.max_chars_per_message}" if not ok else None,
        )

    def _check_must_include(self, text: str, contract: LLMContract) -> ValidationResult:
        lower = text.lower()
        missing = [p for p in contract.must_include if p.lower() not in lower]
        return ValidationResult(
            passed=len(missing) == 0,
            code="must_include",
            reason=f"missing: {missing}" if missing else None,
        )

    def _check_must_not(self, text: str, contract: LLMContract) -> ValidationResult:
        lower = text.lower()
        found = [p for p in contract.must_not if p.lower() in lower]
        return ValidationResult(
            passed=len(found) == 0,
            code="must_not",
            reason=f"found: {found}" if found else None,
        )

    def _check_no_diagnosis(self, text: str) -> ValidationResult:
        for pat in _DIAGNOSIS_PATTERNS:
            m = pat.search(text)
            if m:
                return ValidationResult(
                    passed=False,
                    code="no_diagnosis",
                    reason=f"diagnostic language: {m.group()}",
                    critical=True,
                )
        return ValidationResult(passed=True, code="no_diagnosis")

    def _check_no_medication(self, text: str) -> ValidationResult:
        for pat in _MEDICATION_PATTERNS:
            m = pat.search(text)
            if m:
                return ValidationResult(
                    passed=False,
                    code="no_medication",
                    reason=f"medication language: {m.group()}",
                    critical=True,
                )
        return ValidationResult(passed=True, code="no_medication")

    def _check_language_match(self, text: str, contract: LLMContract) -> ValidationResult:
        if contract.language == "ru":
            # Heuristic: at least 30% Cyrillic characters among letters
            letters = [c for c in text if c.isalpha()]
            if not letters:
                return ValidationResult(passed=True, code="language_match")
            cyrillic = sum(1 for c in letters if "\u0400" <= c <= "\u04ff")
            ratio = cyrillic / len(letters)
            ok = ratio >= 0.3
            return ValidationResult(
                passed=ok,
                code="language_match",
                reason=f"cyrillic ratio {ratio:.2f} < 0.3" if not ok else None,
            )
        elif contract.language == "en":
            letters = [c for c in text if c.isalpha()]
            if not letters:
                return ValidationResult(passed=True, code="language_match")
            latin = sum(1 for c in letters if "a" <= c.lower() <= "z")
            ratio = latin / len(letters)
            ok = ratio >= 0.3
            return ValidationResult(
                passed=ok,
                code="language_match",
                reason=f"latin ratio {ratio:.2f} < 0.3" if not ok else None,
            )
        # Unknown language: pass
        return ValidationResult(passed=True, code="language_match")

    def _check_state_alignment(self, text: str, contract: LLMContract) -> ValidationResult:
        """Simple heuristic: response should not be empty and should loosely
        match the dialogue state expectations."""
        if not text.strip():
            return ValidationResult(
                passed=False,
                code="state_alignment",
                reason="empty response",
            )
        # Crisis / escalation states must not contain humor markers
        if contract.dialogue_state in ("ESCALATION", "SAFETY_CHECK"):
            humor = any(
                m in text.lower()
                for m in ["\U0001f602", "\U0001f923", "lol", "haha", "\u0445\u0430\u0445\u0430"]
            )
            if humor:
                return ValidationResult(
                    passed=False,
                    code="state_alignment",
                    reason="humor in safety/escalation state",
                    critical=True,
                )
        return ValidationResult(passed=True, code="state_alignment")

    def _check_actionability(self, text: str) -> ValidationResult:
        """Check that the response contains at least one actionable element."""
        lower = text.lower()
        markers = [
            "\u0441\u0434\u0435\u043b\u0430\u0439\u0442\u0435", "\u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435", "\u043e\u0446\u0435\u043d\u0438\u0442\u0435", "\u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435", "\u043d\u0430\u0437\u043e\u0432\u0438\u0442\u0435",
            "\u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435", "\u0434\u0430\u0432\u0430\u0439\u0442\u0435", "\u0433\u043e\u0442\u043e\u0432\u044b",
            "tell me", "rate", "choose", "try", "let's", "?",
        ]
        has_action = any(m in lower for m in markers)
        return ValidationResult(
            passed=has_action,
            code="actionability",
            reason="no actionable element found" if not has_action else None,
        )

    def _check_safety_lexicon(self, text: str) -> ValidationResult:
        for pat in _SAFETY_LEXICON_PATTERNS:
            m = pat.search(text)
            if m:
                return ValidationResult(
                    passed=False,
                    code="safety_lexicon",
                    reason=f"harmful content: {m.group()}",
                    critical=True,
                )
        return ValidationResult(passed=True, code="safety_lexicon")


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Trips after ``threshold`` failures within ``window_seconds``."""

    def __init__(self, threshold: int = 3, window_seconds: float = 60.0) -> None:
        self.threshold = threshold
        self.window_seconds = window_seconds
        self._failures: list[float] = []

    def record_failure(self) -> None:
        self._failures.append(time.monotonic())

    def is_open(self) -> bool:
        now = time.monotonic()
        self._failures = [t for t in self._failures if now - t < self.window_seconds]
        return len(self._failures) >= self.threshold

    def reset(self) -> None:
        self._failures.clear()


# ---------------------------------------------------------------------------
# Critical failure codes (immediate fallback, no retry)
# ---------------------------------------------------------------------------

_CRITICAL_CODES = {"no_banned_content", "no_playful_high_risk", "no_diagnosis", "no_medication", "safety_lexicon"}


# ---------------------------------------------------------------------------
# LLMAdapter
# ---------------------------------------------------------------------------

class LLMAdapter:
    """Contract-bound LLM generation with validation and fallback logic.

    Parameters
    ----------
    llm_provider:
        An object with an async ``chat(messages, system, model)`` method.
    model:
        Model identifier for the LLM call.
    max_repeat_count:
        Maximum number of generation attempts (1 original + retries).
    """

    def __init__(
        self,
        llm_provider: object,
        model: str = "claude-sonnet-4-20250514",
        max_repeat_count: int = 2,
    ) -> None:
        self._llm = llm_provider
        self._model = model
        self._max_repeat_count = max_repeat_count
        self._validator = ResponseValidator()
        self._breaker = CircuitBreaker(threshold=3, window_seconds=60.0)

    # -- public API ---------------------------------------------------------

    async def generate(
        self,
        contract: LLMContract,
        risk_level: RiskLevel,
        user_tone_playful: bool = False,
    ) -> str:
        """Generate a response bound by *contract*, validating output.

        Returns validated LLM text or a safe fallback string.
        """
        # Circuit breaker check
        if self._breaker.is_open():
            logger.warning("Circuit breaker open — returning state fallback.")
            return self._get_fallback(contract.dialogue_state)

        system_prompt = self._build_system_prompt(contract)
        messages = self._build_messages(contract)

        for attempt in range(self._max_repeat_count):
            try:
                raw = await self._call_llm(system_prompt, messages)
            except Exception:
                logger.exception("LLM call failed (attempt %d)", attempt + 1)
                self._breaker.record_failure()
                continue

            # --- contract validation (9 checks) ---
            contract_results = self._validator.validate(raw, contract)
            # --- style validation ---
            style_input = StyleValidationInput(
                text=raw,
                risk_level=risk_level,
                user_tone_playful=user_tone_playful,
                long_form_requested=contract.max_chars_per_message > 500,
            )
            style_results = validate_style(style_input)

            # Merge results
            all_failures = [r for r in contract_results if not r.passed]
            style_failures = [r for r in style_results if not r.passed]

            # Check for critical failures -> immediate fallback
            has_critical_contract = any(
                r.critical or r.code in _CRITICAL_CODES for r in all_failures
            )
            has_critical_style = any(
                r.code in _CRITICAL_CODES for r in style_failures
            )

            if has_critical_contract or has_critical_style:
                logger.warning(
                    "Critical validation failure on attempt %d: contract=%s style=%s",
                    attempt + 1,
                    [r.code for r in all_failures if r.critical or r.code in _CRITICAL_CODES],
                    [r.code for r in style_failures if r.code in _CRITICAL_CODES],
                )
                self._breaker.record_failure()
                return self._get_fallback(contract.dialogue_state)

            # Non-critical failures
            if not all_failures and not style_failures:
                # All checks passed
                self._breaker.reset()
                return raw

            # On first attempt with non-critical failures, retry with correction
            if attempt < self._max_repeat_count - 1:
                failure_codes = [r.code for r in all_failures] + [r.code for r in style_failures]
                logger.info("Non-critical failures %s — retrying (attempt %d)", failure_codes, attempt + 1)
                messages = self._build_correction_messages(contract, raw, all_failures, style_failures)
                continue

            # Exhausted retries
            logger.warning("Exhausted retries — returning fallback.")
            self._breaker.record_failure()

        return self._get_fallback(contract.dialogue_state)

    # -- prompt building ----------------------------------------------------

    def _build_system_prompt(self, contract: LLMContract) -> str:
        parts = [STYLE_SYSTEM_PROMPT]
        if contract.persona_summary:
            parts.append(f"\n[PERSONA]\n{contract.persona_summary}")
        if contract.instruction:
            parts.append(f"\n[INSTRUCTION]\n{contract.instruction}")
        parts.append(f"\n[GENERATION TASK]\n{contract.generation_task}")
        parts.append(f"\n[CONSTRAINTS]\nmax_chars: {contract.max_chars_per_message}")
        if contract.must_include:
            parts.append(f"must_include phrases: {contract.must_include}")
        if contract.must_not:
            parts.append(f"must_not contain: {contract.must_not}")
        parts.append(f"language: {contract.language}")
        return "\n".join(parts)

    def _build_messages(self, contract: LLMContract) -> list[dict]:
        messages: list[dict] = []
        for m in contract.recent_messages:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        if contract.user_summary:
            messages.append({"role": "user", "content": f"[User context: {contract.user_summary}]"})
        if contract.user_response_to:
            messages.append({"role": "user", "content": contract.user_response_to})
        return messages or [{"role": "user", "content": contract.generation_task}]

    def _build_correction_messages(
        self,
        contract: LLMContract,
        raw: str,
        contract_failures: list[ValidationResult],
        style_failures: list[CheckResult],
    ) -> list[dict]:
        issues = []
        for r in contract_failures:
            issues.append(f"- {r.code}: {r.reason or 'failed'}")
        for r in style_failures:
            issues.append(f"- {r.code}: {r.reason or 'failed'}")

        correction = (
            f"Your previous response had these issues:\n"
            + "\n".join(issues)
            + "\n\nPlease regenerate, fixing the issues above. "
            f"Keep within {contract.max_chars_per_message} chars, language={contract.language}."
        )
        base = self._build_messages(contract)
        base.append({"role": "assistant", "content": raw})
        base.append({"role": "user", "content": correction})
        return base

    # -- LLM call -----------------------------------------------------------

    async def _call_llm(self, system: str, messages: list[dict]) -> str:
        response = await self._llm.chat(
            messages=messages,
            system=system,
            model=self._model,
        )
        return response.content

    # -- fallback -----------------------------------------------------------

    def _get_fallback(self, dialogue_state: str) -> str:
        return STATE_FALLBACKS.get(dialogue_state, DEFAULT_FALLBACK)
