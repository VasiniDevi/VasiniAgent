"""Two-layer safety classifier: hard rules + LLM."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from wellness_bot.protocol.types import RiskLevel


@dataclass
class SafetyResult:
    risk_level: RiskLevel
    protocol_id: str | None = None
    immediacy: str = "none"  # none | possible | imminent
    signals: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = "rules"  # rules | model | heuristic
    classifier_version: str = "1.0"
    policy_version: str = "1.0"

    def message_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()


# Hard-coded crisis patterns — Layer 1
_CRISIS_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, protocol_id, signal_name)
    # S1: Suicide / Self-harm
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
    # S3: Psychosis
    (r"голоса\s+говорят", "S3", "psychosis_hallucination_ru"),
    (r"за\s+мной\s+следят", "S3", "psychosis_paranoia_ru"),
    (r"я\s+избранн", "S3", "psychosis_grandiosity_ru"),
    # S6: Domestic violence
    (r"(муж|парень|партн[её]р)\s+(бь[её]т|удари)", "S6", "dv_physical_ru"),
    (r"бь[её]т\s+меня", "S6", "dv_physical_ru"),
    (r"боюсь\s+партн[её]р", "S6", "dv_fear_ru"),
]

_COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), proto, sig) for p, proto, sig in _CRISIS_PATTERNS]


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
        for pattern, protocol_id, signal_name in _COMPILED_PATTERNS:
            if pattern.search(text):
                return SafetyResult(
                    risk_level=RiskLevel.CRISIS,
                    protocol_id=protocol_id,
                    immediacy="possible",
                    signals=[signal_name],
                    confidence=1.0,
                    source="rules",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )
        return None

    async def classify(self, text: str, context: list[dict]) -> SafetyResult:
        """Full two-layer classification: hard rules first, then LLM."""
        # Layer 1: hard rules
        hard_result = self.check_hard_rules(text)
        if hard_result is not None:
            return hard_result

        # Layer 2: LLM classifier (if available)
        if self._llm is not None:
            return await self._classify_with_llm(text, context)

        # No LLM available: uncertain → CAUTION_MILD (never SAFE when uncertain)
        return SafetyResult(
            risk_level=RiskLevel.CAUTION_MILD,
            signals=["no_llm_classifier"],
            confidence=0.0,
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
            "Classify this message for risk level. "
            'Respond ONLY with JSON: {"risk_level":"SAFE|CAUTION_MILD|CAUTION_ELEVATED|CRISIS",'
            '"protocol":null or "S1"|"S2"|"S3"|"S4"|"S5"|"S6"|"S7",'
            '"immediacy":"none|possible|imminent",'
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

            risk = RiskLevel(data["risk_level"])
            confidence = float(data.get("confidence", 0.5))

            # Classification logic per design:
            if confidence >= 0.7:
                return SafetyResult(
                    risk_level=risk,
                    protocol_id=data.get("protocol"),
                    immediacy=data.get("immediacy", "none"),
                    signals=data.get("signals", []),
                    confidence=confidence,
                    source="model",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )
            elif risk == RiskLevel.CRISIS:
                # Safety > precision: escalate even at low confidence
                return SafetyResult(
                    risk_level=RiskLevel.CRISIS,
                    protocol_id=data.get("protocol"),
                    immediacy=data.get("immediacy", "possible"),
                    signals=data.get("signals", []) + ["low_confidence_crisis"],
                    confidence=confidence,
                    source="model",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )
            else:
                # Low confidence, not crisis → CAUTION_MILD (never SAFE when uncertain)
                return SafetyResult(
                    risk_level=RiskLevel.CAUTION_MILD,
                    signals=data.get("signals", []) + ["low_confidence"],
                    confidence=confidence,
                    source="model",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )

        except Exception:
            # LLM failed → uncertain → CAUTION_MILD
            return SafetyResult(
                risk_level=RiskLevel.CAUTION_MILD,
                signals=["llm_error"],
                confidence=0.0,
                source="heuristic",
                classifier_version=self.classifier_version,
                policy_version=self.policy_version,
            )
