"""Two-layer safety classifier: hard rules + LLM.

Non-blocking soft levels: agent ALWAYS helps, NEVER refuses.
- GREEN: normal — help freely
- YELLOW: suggest specialist alongside help
- RED: provide crisis resources + stay available
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from wellness_bot.protocol.types import RiskLevel, SafetyLevel


_CRISIS_RESOURCES = {
    "ru": (
        "Телефон доверия: 8-800-2000-122 (бесплатно, круглосуточно). "
        "Ты не одна/один. Я здесь."
    ),
    "en": (
        "Crisis line: 988 (Suicide & Crisis Lifeline, US) or text HOME to 741741. "
        "You're not alone. I'm here."
    ),
}

_SPECIALIST_SUGGESTION = {
    "ru": (
        "Кстати, с этим также могут помочь специалисты — "
        "хочешь, подскажу как найти?"
    ),
    "en": (
        "By the way, a specialist could also help with this — "
        "want me to suggest how to find one?"
    ),
}


@dataclass
class SafetyResult:
    """Safety classification result — never blocks practice access."""
    safety_level: SafetyLevel = SafetyLevel.GREEN
    protocol_id: str | None = None
    signals: list[str] = field(default_factory=list)
    confidence: float = 1.0
    specialist_suggestion: str | None = None
    crisis_resources: str | None = None
    block_practice: bool = False  # ALWAYS False — safety never blocks

    # Legacy fields for backward compatibility
    risk_level: RiskLevel = RiskLevel.SAFE
    immediacy: str = "none"
    source: str = "rules"
    classifier_version: str = "1.0"
    policy_version: str = "1.0"

    def message_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Hard-coded patterns — Layer 1
# ---------------------------------------------------------------------------

# RED patterns: only explicit suicidal plan/intent
_RED_PATTERNS: list[tuple[str, str, str]] = [
    # S1: Suicide / Self-harm — explicit intent
    (r"хочу\s+умереть", "S1", "suicide_explicit_ru"),
    (r"покончить\s+с\s+собой", "S1", "suicide_explicit_ru"),
    (r"суицид", "S1", "suicide_keyword_ru"),
    (r"убить\s+себя", "S1", "suicide_explicit_ru"),
    (r"не\s+хочу\s+жить", "S1", "suicide_wish_ru"),
    (r"лучше\s+бы\s+меня\s+не\s+было", "S1", "suicide_wish_ru"),
    (r"kill\s+my\s*self", "S1", "suicide_explicit_en"),
    (r"want\s+to\s+die", "S1", "suicide_explicit_en"),
    (r"end\s+my\s+life", "S1", "suicide_explicit_en"),
    (r"реж[уе]\s+себ[яе]", "S1", "self_harm_ru"),
    (r"причин(ить|яю)\s+себе\s+(боль|вред)", "S1", "self_harm_ru"),
    (r"hurt\s+my\s*self", "S1", "self_harm_en"),
    # S2: Violence to others
    (r"убь[юёе]\s+(его|её|их|тебя)", "S2", "violence_threat_ru"),
    (r"хочу\s+навредить", "S2", "violence_intent_ru"),
    (r"kill\s+(him|her|them)", "S2", "violence_threat_en"),
]

# YELLOW patterns: severe states where specialist suggestion is warranted
_YELLOW_PATTERNS: list[tuple[str, str, str]] = [
    # S3: Psychosis signals
    (r"голоса\s+говорят", "S3", "psychosis_hallucination_ru"),
    (r"за\s+мной\s+следят", "S3", "psychosis_paranoia_ru"),
    (r"я\s+избранн", "S3", "psychosis_grandiosity_ru"),
    # S6: Domestic violence
    (r"(муж|парень|партн[её]р)\s+(бь[её]т|удари)", "S6", "dv_physical_ru"),
    (r"бь[её]т\s+меня", "S6", "dv_physical_ru"),
    (r"боюсь\s+партн[её]р", "S6", "dv_fear_ru"),
]

_COMPILED_RED = [(re.compile(p, re.IGNORECASE), proto, sig) for p, proto, sig in _RED_PATTERNS]
_COMPILED_YELLOW = [(re.compile(p, re.IGNORECASE), proto, sig) for p, proto, sig in _YELLOW_PATTERNS]


class SafetyClassifier:
    def __init__(
        self,
        classifier_version: str = "1.0",
        policy_version: str = "1.0",
        llm_provider: object = None,
    ) -> None:
        self.classifier_version = classifier_version
        self.policy_version = policy_version
        self._llm = llm_provider

    def check_hard_rules(self, text: str) -> SafetyResult | None:
        """Layer 1: instant pattern matching. Returns None if no match."""
        # Check RED patterns first (suicide/violence)
        for pattern, protocol_id, signal_name in _COMPILED_RED:
            if pattern.search(text):
                return SafetyResult(
                    safety_level=SafetyLevel.RED,
                    protocol_id=protocol_id,
                    signals=[signal_name],
                    confidence=1.0,
                    crisis_resources=_CRISIS_RESOURCES.get("ru"),
                    block_practice=False,
                    # Legacy compat
                    risk_level=RiskLevel.CRISIS,
                    immediacy="possible",
                    source="rules",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )

        # Check YELLOW patterns (psychosis, DV)
        for pattern, protocol_id, signal_name in _COMPILED_YELLOW:
            if pattern.search(text):
                return SafetyResult(
                    safety_level=SafetyLevel.YELLOW,
                    protocol_id=protocol_id,
                    signals=[signal_name],
                    confidence=1.0,
                    specialist_suggestion=_SPECIALIST_SUGGESTION.get("ru"),
                    block_practice=False,
                    # Legacy compat
                    risk_level=RiskLevel.CAUTION_ELEVATED,
                    immediacy="possible",
                    source="rules",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )

        return None

    async def classify(self, text: str, context: list[dict] | None = None) -> SafetyResult:
        """Full two-layer classification: hard rules first, then LLM.

        Safety NEVER blocks. Result is informational — adds context
        for the response generator but never prevents help.
        """
        context = context or []

        # Layer 1: hard rules
        hard_result = self.check_hard_rules(text)
        if hard_result is not None:
            return hard_result

        # Layer 2: LLM classifier (if available)
        if self._llm is not None:
            return await self._classify_with_llm(text, context)

        # No LLM available → GREEN (agent helps freely)
        return SafetyResult(
            safety_level=SafetyLevel.GREEN,
            signals=["no_llm_classifier"],
            confidence=0.0,
            block_practice=False,
            # Legacy compat
            risk_level=RiskLevel.SAFE,
            source="heuristic",
            classifier_version=self.classifier_version,
            policy_version=self.policy_version,
        )

    async def _classify_with_llm(self, text: str, context: list[dict]) -> SafetyResult:
        """Layer 2: LLM-based classification using haiku."""
        import json

        context_str = " | ".join(
            f"{m.get('role', '?')}: {m.get('content', '')[:100]}"
            for m in context[-3:]
        )

        system = (
            "You are a safety classifier for a wellness bot. "
            "Classify this message into safety levels. "
            'Respond ONLY with JSON: {"safety_level":"green|yellow|red",'
            '"protocol":null or "S1"|"S2"|"S3"|"S4"|"S5"|"S6"|"S7",'
            '"signals":["list"],"confidence":0.0-1.0}'
        )

        prompt = f"User message: \"{text}\"\nRecent context: \"{context_str}\""

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system=system,
                model="claude-haiku-4-5-20251001",
            )
            data = json.loads(response.content)

            level_str = data.get("safety_level", "green").lower()
            confidence = float(data.get("confidence", 0.5))

            # Map LLM response to SafetyLevel
            if level_str == "red" or confidence >= 0.7 and level_str == "red":
                safety_level = SafetyLevel.RED
                risk_level = RiskLevel.CRISIS
            elif level_str == "yellow":
                safety_level = SafetyLevel.YELLOW
                risk_level = RiskLevel.CAUTION_ELEVATED
            else:
                safety_level = SafetyLevel.GREEN
                risk_level = RiskLevel.SAFE

            # Low confidence RED still escalates (safety > precision)
            if level_str == "red" and confidence < 0.7:
                safety_level = SafetyLevel.RED
                risk_level = RiskLevel.CRISIS
                data.setdefault("signals", []).append("low_confidence_crisis")

            return SafetyResult(
                safety_level=safety_level,
                protocol_id=data.get("protocol"),
                signals=data.get("signals", []),
                confidence=confidence,
                specialist_suggestion=_SPECIALIST_SUGGESTION.get("ru") if safety_level == SafetyLevel.YELLOW else None,
                crisis_resources=_CRISIS_RESOURCES.get("ru") if safety_level == SafetyLevel.RED else None,
                block_practice=False,
                risk_level=risk_level,
                immediacy=data.get("immediacy", "none"),
                source="model",
                classifier_version=self.classifier_version,
                policy_version=self.policy_version,
            )

        except Exception:
            # LLM failed → GREEN (agent helps, doesn't block)
            return SafetyResult(
                safety_level=SafetyLevel.GREEN,
                signals=["llm_error"],
                confidence=0.0,
                block_practice=False,
                risk_level=RiskLevel.SAFE,
                source="heuristic",
                classifier_version=self.classifier_version,
                policy_version=self.policy_version,
            )
