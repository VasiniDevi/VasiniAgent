"""Coaching pipeline — wires all 11 components into the main processing flow.

This is the central integration point that orchestrates:

1. Safety Gate (crisis detection)
2. Language Resolver
3. Context Analyzer (LLM)
4. Opportunity Scorer
5. Practice Selector
6. Coach Policy Engine
7. Response Generator (LLM)
8. Output Safety Check
9. Suggestion tracking
10. FSM transition
11. Audit logging
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from wellness_bot.coaching.safety_gate import SafetyGate
from wellness_bot.coaching.language_resolver import LanguageResolver
from wellness_bot.coaching.context_analyzer import ContextAnalyzer
from wellness_bot.coaching.opportunity_scorer import OpportunityScorer
from wellness_bot.coaching.practice_selector import PracticeSelector, PracticeCatalogEntry
from wellness_bot.coaching.coach_policy import CoachPolicyEngine
from wellness_bot.coaching.output_safety import OutputSafetyCheck
from wellness_bot.coaching.fsm import ConversationFSM
from wellness_bot.protocol.types import CoachingDecision

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Crisis response templates by language
# ---------------------------------------------------------------------------

_CRISIS_RESPONSES = {
    "ru": (
        "Я слышу тебя. То, что ты чувствуешь — серьёзно, и ты заслуживаешь "
        "помощи прямо сейчас.\n\n"
        "Пожалуйста, позвони на линию помощи: 8-800-2000-122 "
        "(бесплатно, круглосуточно).\n\n"
        "Я здесь и могу поговорить, но профессиональная помощь "
        "сейчас важнее всего."
    ),
    "en": (
        "I hear you. What you're feeling is serious, and you deserve help "
        "right now.\n\n"
        "Please call a crisis line: 988 (Suicide & Crisis Lifeline, US) "
        "or text HOME to 741741.\n\n"
        "I'm here and can talk, but professional help is the most important "
        "thing right now."
    ),
    "es": (
        "Te escucho. Lo que sientes es serio y mereces ayuda ahora mismo.\n\n"
        "Por favor llama a la línea de crisis: 024 (España) o tu línea "
        "local de ayuda.\n\n"
        "Estoy aquí y puedo hablar, pero la ayuda profesional es lo más "
        "importante ahora."
    ),
}

# ---------------------------------------------------------------------------
# Safe fallback responses by language
# ---------------------------------------------------------------------------

_SAFE_FALLBACKS = {
    "ru": "Я здесь и слушаю. Расскажи, что тебя беспокоит?",
    "en": "I'm here and listening. Tell me what's on your mind?",
    "es": "Estoy aquí y escucho. Cuéntame qué te preocupa.",
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class PipelineConfig:
    """Configuration for the coaching pipeline."""

    db_path: str = "data/wellness.db"
    response_model: str = "claude-sonnet-4-5-20250929"
    context_model: str = "claude-haiku-4-5-20251001"
    max_dialogue_window: int = 10


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class CoachingPipeline:
    """Main coaching pipeline that wires all 11 components together.

    Parameters
    ----------
    llm_provider:
        An object with an async ``chat(messages, system, model)`` method.
    config:
        Pipeline configuration. Uses defaults if not provided.
    catalog:
        Practice catalog entries for the PracticeSelector. If not provided,
        an empty catalog is used.
    """

    def __init__(
        self,
        llm_provider: object,
        config: PipelineConfig | None = None,
        catalog: list[PracticeCatalogEntry] | None = None,
    ) -> None:
        self._config = config or PipelineConfig()
        self._llm = llm_provider

        # Initialize all components
        self._safety_gate = SafetyGate()
        self._language_resolver = LanguageResolver()
        self._context_analyzer = ContextAnalyzer(
            llm_provider=llm_provider,
            model=self._config.context_model,
        )
        self._opportunity_scorer = OpportunityScorer()
        self._practice_selector = PracticeSelector(catalog or [])
        self._coach_policy = CoachPolicyEngine()
        self._output_safety = OutputSafetyCheck()

        # Per-user state
        self._fsm: dict[str, ConversationFSM] = {}
        self._dialogue: dict[str, list[dict[str, str]]] = {}
        self._suggestion_history: dict[str, list[dict]] = {}
        self._messages_since_suggest: dict[str, int] = {}

    def _get_fsm(self, user_id: str) -> ConversationFSM:
        """Get or create a ConversationFSM for a user."""
        if user_id not in self._fsm:
            self._fsm[user_id] = ConversationFSM()
        return self._fsm[user_id]

    async def process(self, user_id: str, text: str) -> str:
        """Process a user message through the 11-step coaching pipeline.

        Parameters
        ----------
        user_id:
            Unique identifier for the user.
        text:
            The user's message text.

        Returns
        -------
        str
            The bot's response text.
        """
        start_time = time.monotonic()
        fsm = self._get_fsm(user_id)

        # ── Step 1: Safety Gate ───────────────────────────────────────
        safety_result = self._safety_gate.check(text)
        if safety_result.risk_level == "crisis":
            fsm.enter_crisis()
            language = self._language_resolver.resolve(user_id, text)
            response = _CRISIS_RESPONSES.get(language, _CRISIS_RESPONSES["en"])
            logger.info(
                "AUDIT | user=%s step=safety_gate result=crisis signals=%s",
                user_id,
                safety_result.signals,
            )
            return response

        # ── Step 2: Language Resolver ─────────────────────────────────
        language = self._language_resolver.resolve(user_id, text)

        # ── Dialogue window management ────────────────────────────────
        if user_id not in self._dialogue:
            self._dialogue[user_id] = []
        self._dialogue[user_id].append({"role": "user", "content": text})

        # Trim to max window size
        max_window = self._config.max_dialogue_window
        if len(self._dialogue[user_id]) > max_window:
            self._dialogue[user_id] = self._dialogue[user_id][-max_window:]

        dialogue_window = self._dialogue[user_id]

        # ── Step 3: Context Analyzer ──────────────────────────────────
        context = await self._context_analyzer.analyze(
            user_message=text,
            dialogue_window=dialogue_window,
            mood_history=[],
            practice_history=[],
            user_profile={},
            language=language,
        )

        # ── Step 4: Opportunity Scorer ────────────────────────────────
        recent_suggestions = self._suggestion_history.get(user_id, [])
        messages_since = self._messages_since_suggest.get(user_id, 0)

        opportunity = self._opportunity_scorer.score(
            context=context,
            recent_suggestions=recent_suggestions,
            messages_since_last_suggest=messages_since,
        )

        # ── Step 5: Practice Selector ─────────────────────────────────
        ranked_practices = []
        if opportunity.allow_proactive_suggest:
            ranked_practices = self._practice_selector.select(
                context=context,
                opportunity_score=opportunity.opportunity_score,
                user_history={},
                top_k=3,
            )

        # ── Step 6: Coach Policy ──────────────────────────────────────
        decision = self._coach_policy.decide(
            context=context,
            opportunity=opportunity,
            ranked_practices=ranked_practices,
        )

        # ── Step 7: Response Generator ────────────────────────────────
        response = await self._generate_response(
            user_message=text,
            dialogue_window=dialogue_window,
            decision=decision.decision,
            language=language,
            practice_id=decision.selected_practice_id,
            style=decision.style,
        )

        # ── Step 8: Output Safety Check ───────────────────────────────
        safety_check = self._output_safety.validate(response)
        if not safety_check.approved:
            logger.warning(
                "AUDIT | user=%s step=output_safety reason=%s action=%s",
                user_id,
                safety_check.reason,
                safety_check.action,
            )
            response = self._safe_fallback(language, decision.decision)

        # ── Step 9: Track suggestion ──────────────────────────────────
        if decision.decision == CoachingDecision.SUGGEST:
            if user_id not in self._suggestion_history:
                self._suggestion_history[user_id] = []
            self._suggestion_history[user_id].append({
                "practice_id": decision.selected_practice_id,
                "outcome": "pending",
            })
            self._messages_since_suggest[user_id] = 0
        else:
            self._messages_since_suggest[user_id] = messages_since + 1

        # ── Step 10: FSM transition ───────────────────────────────────
        fsm.transition(decision.decision)

        # ── Step 11: Audit log ────────────────────────────────────────
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "AUDIT | user=%s decision=%s practice=%s opportunity=%.2f "
            "language=%s latency_ms=%d fsm_state=%s",
            user_id,
            decision.decision.value,
            decision.selected_practice_id,
            opportunity.opportunity_score,
            language,
            elapsed_ms,
            fsm.conversation_state.value,
        )

        # Add assistant response to dialogue window
        self._dialogue[user_id].append({"role": "assistant", "content": response})

        return response

    async def _generate_response(
        self,
        *,
        user_message: str,
        dialogue_window: list[dict[str, str]],
        decision: CoachingDecision,
        language: str,
        practice_id: str | None = None,
        style: str = "warm_supportive",
    ) -> str:
        """Generate a response using the LLM based on the coaching decision.

        Parameters
        ----------
        user_message:
            The user's latest message.
        dialogue_window:
            Recent dialogue history.
        decision:
            The coaching decision (LISTEN, EXPLORE, SUGGEST, GUIDE, ANSWER).
        language:
            ISO 639-1 language code.
        practice_id:
            Selected practice ID (only for SUGGEST decision).
        style:
            Coaching style to use.

        Returns
        -------
        str
            Generated response text, or a safe fallback on failure.
        """
        # Build system prompt based on decision
        role_prompts = {
            CoachingDecision.LISTEN: (
                "You are an empathetic listener. Reflect the user's feelings, "
                "validate their experience, and show you are present. "
                "Do NOT suggest exercises or practices."
            ),
            CoachingDecision.EXPLORE: (
                "You are a curious coach. Ask open-ended questions to understand "
                "the user's situation better. Be warm and non-judgmental."
            ),
            CoachingDecision.SUGGEST: (
                f"You are a proactive coach. Gently suggest practice "
                f"'{practice_id}' as something that might help. Ask for consent "
                f"before starting. Be warm and non-pressuring."
            ),
            CoachingDecision.GUIDE: (
                "You are a gentle coach. Acknowledge the user's feelings and "
                "offer light psychoeducation or reframing. Do NOT push "
                "specific exercises yet."
            ),
            CoachingDecision.ANSWER: (
                "You are a helpful assistant. Answer the user's question "
                "directly and concisely."
            ),
        }

        role_prompt = role_prompts.get(decision, role_prompts[CoachingDecision.LISTEN])

        system_prompt = (
            f"{role_prompt}\n\n"
            f"Respond in {language}. Keep response to 1-3 sentences. "
            f"You are a wellness support coach, NOT a therapist. "
            f"Never diagnose or prescribe medication."
        )

        # Build messages for the LLM
        messages = [{"role": m["role"], "content": m["content"]} for m in dialogue_window]

        try:
            response = await self._llm.chat(
                messages=messages,
                system=system_prompt,
                model=self._config.response_model,
            )
            return response.content
        except Exception:
            logger.exception("LLM call failed in _generate_response")
            return self._safe_fallback(language, decision)

    def _safe_fallback(self, language: str, decision: CoachingDecision) -> str:
        """Return a safe fallback response in the user's language.

        Parameters
        ----------
        language:
            ISO 639-1 language code.
        decision:
            The coaching decision (unused but available for future refinement).

        Returns
        -------
        str
            A safe, generic response in the appropriate language.
        """
        return _SAFE_FALLBACKS.get(language, _SAFE_FALLBACKS["en"])
