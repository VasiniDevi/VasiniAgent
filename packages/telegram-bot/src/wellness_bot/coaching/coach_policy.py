"""Coach Policy Engine — makes the final coaching decision.

Takes the conversation context, opportunity score, and ranked practice
candidates as inputs and returns a single :class:`CoachDecision` that
tells the response generator what to do next.

The decision rules are evaluated top-to-bottom in strict priority order:

1. Crisis override         -> LISTEN  (no practice)
2. No signal / no practices -> ANSWER
3. Low confidence          -> EXPLORE
4. Opportunity not allowed -> EXPLORE or LISTEN
5. Strong practice match   -> SUGGEST
6. Signals but weak match  -> GUIDE
7. Default                 -> LISTEN
"""

from __future__ import annotations

from wellness_bot.protocol.types import (
    CoachDecision,
    CoachingDecision,
    ContextState,
    OpportunityResult,
    PracticeCandidateRanked,
)

# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------

SUGGEST_SCORE_THRESHOLD: float = 0.58
EXPLORE_CONFIDENCE_THRESHOLD: float = 0.5


class CoachPolicyEngine:
    """Deterministic policy that picks the coaching action for a turn."""

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def decide(
        self,
        context: ContextState,
        opportunity: OpportunityResult,
        ranked_practices: list[PracticeCandidateRanked],
    ) -> CoachDecision:
        """Return the final coaching decision for this conversational turn.

        Parameters
        ----------
        context:
            Current conversation context including risk level, emotional
            state, readiness, confidence, and hypotheses.
        opportunity:
            Result from the :class:`OpportunityScorer` — includes the
            opportunity score and an allow/block flag.
        ranked_practices:
            Practices ranked by the practice ranker, ordered by
            ``final_score`` descending.  May be empty.

        Returns
        -------
        CoachDecision
            Dataclass with ``decision``, optional ``selected_practice_id``,
            ``style``, and ``must_ask_consent``.
        """

        # -- derived helpers ------------------------------------------------
        es = context.emotional_state
        max_signal = max(
            es.anxiety,
            es.rumination,
            es.avoidance,
            es.perfectionism,
            es.self_criticism,
            es.symptom_fixation,
        )

        # -- Rule 1: Crisis -------------------------------------------------
        if context.risk_level in ("high", "crisis"):
            return CoachDecision(
                decision=CoachingDecision.LISTEN,
                style="warm_supportive",
            )

        # -- Rule 2: No signal + no practices --------------------------------
        if max_signal < 0.15 and not ranked_practices:
            return CoachDecision(
                decision=CoachingDecision.ANSWER,
                style="direct_helpful",
            )

        # -- Rule 3: Low confidence ------------------------------------------
        if context.confidence < EXPLORE_CONFIDENCE_THRESHOLD:
            return CoachDecision(
                decision=CoachingDecision.EXPLORE,
                style="warm_curious",
            )

        # -- Rule 4: Opportunity not allowed ---------------------------------
        if not opportunity.allow_proactive_suggest:
            if max_signal > 0.4:
                return CoachDecision(
                    decision=CoachingDecision.EXPLORE,
                    style="warm_curious",
                )
            return CoachDecision(
                decision=CoachingDecision.LISTEN,
                style="warm_supportive",
            )

        # -- Rule 5: Top practice strong enough ------------------------------
        if ranked_practices:
            top = ranked_practices[0]
            if top.final_score >= SUGGEST_SCORE_THRESHOLD:
                return CoachDecision(
                    decision=CoachingDecision.SUGGEST,
                    selected_practice_id=top.practice_id,
                    style="warm_directive",
                    must_ask_consent=True,
                )

        # -- Rule 6: Signals present but no strong match ---------------------
        if max_signal > 0.3:
            return CoachDecision(
                decision=CoachingDecision.GUIDE,
                style="warm_curious",
            )

        # -- Rule 7: Default -------------------------------------------------
        return CoachDecision(
            decision=CoachingDecision.LISTEN,
            style="warm_supportive",
        )
