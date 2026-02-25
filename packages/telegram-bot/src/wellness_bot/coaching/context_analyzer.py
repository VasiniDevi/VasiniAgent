"""LLM-based analysis of user state from dialogue and DB history.

Step 3 in the coaching pipeline. Uses an LLM to infer emotional state,
risk level, readiness for practice, and coaching hypotheses from the
current message, recent dialogue window, and historical data.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from wellness_bot.protocol.types import ContextState, EmotionalState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt for context analysis
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert clinical context analyzer for a CBT/MCT wellness coaching bot.

Your task: analyze the user's current emotional and psychological context based on
their latest message, recent dialogue history, mood trends, and practice history.

Return ONLY valid JSON with this exact schema (no extra text, no markdown fences):
{
  "risk_level": "low|medium|high|crisis",
  "emotional_state": {
    "anxiety": 0.0-1.0,
    "rumination": 0.0-1.0,
    "avoidance": 0.0-1.0,
    "perfectionism": 0.0-1.0,
    "self_criticism": 0.0-1.0,
    "symptom_fixation": 0.0-1.0
  },
  "readiness_for_practice": 0.0-1.0,
  "coaching_hypotheses": ["string"],
  "confidence": 0.0-1.0,
  "candidate_constraints": ["string"]
}

Guidelines:
- risk_level: "low" = no concern, "medium" = mild distress, "high" = significant distress, "crisis" = immediate safety concern
- emotional_state: rate each maintaining cycle dimension from 0.0 (absent) to 1.0 (dominant)
- readiness_for_practice: 0.0 = not ready at all, 1.0 = fully ready and willing
- coaching_hypotheses: brief clinical hypotheses about what maintains the user's current state
- confidence: your confidence in this analysis (0.0-1.0)
- candidate_constraints: any constraints on practice selection (e.g. "no_breathing" if user resists breathing exercises)

Be conservative with risk levels. When uncertain, lean toward lower confidence rather than lower risk.
"""


class ContextAnalyzer:
    """LLM-based analyzer that infers user context from dialogue and history.

    Parameters
    ----------
    llm_provider:
        An object with an async ``chat(messages, system, model)`` method.
    model:
        Model identifier for the LLM call.
    """

    def __init__(
        self,
        llm_provider: object,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self._llm = llm_provider
        self._model = model

    async def analyze(
        self,
        user_message: str,
        dialogue_window: list[dict[str, Any]],
        mood_history: list[dict[str, Any]],
        practice_history: list[dict[str, Any]],
        user_profile: dict[str, Any],
        language: str,
    ) -> ContextState:
        """Analyze user context and return a structured ContextState.

        Never raises — returns safe defaults on any failure.
        """
        try:
            prompt = self._build_user_prompt(
                user_message=user_message,
                dialogue_window=dialogue_window,
                mood_history=mood_history,
                practice_history=practice_history,
                user_profile=user_profile,
                language=language,
            )
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system=SYSTEM_PROMPT,
                model=self._model,
            )
            return self._parse_response(response.content)
        except Exception:
            logger.exception("LLM call failed in ContextAnalyzer — returning safe defaults")
            return _safe_defaults(confidence=0.2)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        *,
        user_message: str,
        dialogue_window: list[dict[str, Any]],
        mood_history: list[dict[str, Any]],
        practice_history: list[dict[str, Any]],
        user_profile: dict[str, Any],
        language: str,
    ) -> str:
        """Assemble the user-role prompt from all available data."""
        parts: list[str] = []

        parts.append(f"[Language: {language}]")

        if user_profile:
            parts.append(f"[User profile]\n{json.dumps(user_profile, ensure_ascii=False, default=str)}")

        if mood_history:
            parts.append(f"[Mood history]\n{json.dumps(mood_history, ensure_ascii=False, default=str)}")

        if practice_history:
            parts.append(f"[Practice history]\n{json.dumps(practice_history, ensure_ascii=False, default=str)}")

        if dialogue_window:
            formatted = "\n".join(
                f"{m.get('role', 'unknown')}: {m.get('content', '')}"
                for m in dialogue_window
            )
            parts.append(f"[Recent dialogue]\n{formatted}")

        parts.append(f"[Current message]\n{user_message}")

        return "\n\n".join(parts)

    def _parse_response(self, text: str) -> ContextState:
        """Parse LLM JSON response into ContextState.

        Returns safe defaults (confidence=0.3) on any parse failure.
        """
        try:
            # Strip markdown fences if present
            cleaned = text.strip()
            if cleaned.startswith("```"):
                # Remove opening fence (with optional language tag)
                first_newline = cleaned.index("\n")
                cleaned = cleaned[first_newline + 1 :]
            if cleaned.endswith("```"):
                cleaned = cleaned[: -3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            # Extract emotional state with defaults
            es_raw = data.get("emotional_state", {})
            emotional_state = EmotionalState(
                anxiety=float(es_raw.get("anxiety", 0.0)),
                rumination=float(es_raw.get("rumination", 0.0)),
                avoidance=float(es_raw.get("avoidance", 0.0)),
                perfectionism=float(es_raw.get("perfectionism", 0.0)),
                self_criticism=float(es_raw.get("self_criticism", 0.0)),
                symptom_fixation=float(es_raw.get("symptom_fixation", 0.0)),
            )

            return ContextState(
                risk_level=str(data.get("risk_level", "low")),
                emotional_state=emotional_state,
                readiness_for_practice=float(data.get("readiness_for_practice", 0.5)),
                coaching_hypotheses=list(data.get("coaching_hypotheses", [])),
                confidence=float(data.get("confidence", 0.5)),
                candidate_constraints=list(data.get("candidate_constraints", [])),
            )
        except Exception:
            logger.warning("Failed to parse LLM context response — returning safe defaults")
            return _safe_defaults(confidence=0.3)


def _safe_defaults(confidence: float) -> ContextState:
    """Return a safe, neutral ContextState for error scenarios."""
    return ContextState(
        risk_level="low",
        emotional_state=EmotionalState(),
        readiness_for_practice=0.5,
        coaching_hypotheses=[],
        confidence=confidence,
        candidate_constraints=[],
    )
