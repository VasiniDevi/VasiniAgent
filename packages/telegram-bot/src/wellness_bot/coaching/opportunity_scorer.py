"""Proactive opportunity scorer — decides whether to suggest a practice.

Scores how appropriate it is to proactively offer a practice based on
emotional signals, user readiness, consecutive declines, and message
cadence.  Returns an OpportunityResult with a 0-1 score, an allow flag,
reason codes, and an optional cooldown timestamp.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wellness_bot.protocol.types import ContextState, OpportunityResult

# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------

MIN_MESSAGES_BETWEEN_SUGGESTS: int = 3
MAX_CONSECUTIVE_DECLINES: int = 2
COOLDOWN_HOURS_AFTER_DECLINES: int = 24
OPPORTUNITY_THRESHOLD: float = 0.60


class OpportunityScorer:
    """Score whether it is appropriate to proactively suggest a practice."""

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def score(
        self,
        context: ContextState,
        recent_suggestions: list[dict],
        messages_since_last_suggest: int,
    ) -> OpportunityResult:
        """Evaluate the opportunity to proactively suggest a practice.

        Parameters
        ----------
        context:
            Current conversation context including risk level, emotional
            state, readiness, and confidence.
        recent_suggestions:
            List of past suggestion dicts, each containing at least an
            ``"outcome"`` key (``"accepted"`` or ``"declined"``).  Ordered
            chronologically (oldest first).
        messages_since_last_suggest:
            Number of user messages since the last suggestion was made.

        Returns
        -------
        OpportunityResult
            Dataclass with ``opportunity_score``, ``allow_proactive_suggest``,
            ``reason_codes``, and optional ``cooldown_until``.
        """

        # 1. Risk-level gate --------------------------------------------------
        if context.risk_level in ("high", "crisis"):
            return OpportunityResult(
                opportunity_score=0.0,
                allow_proactive_suggest=False,
                reason_codes=["risk_level_too_high"],
            )

        # 2. Minimum message cadence ------------------------------------------
        if messages_since_last_suggest < MIN_MESSAGES_BETWEEN_SUGGESTS:
            return OpportunityResult(
                opportunity_score=0.0,
                allow_proactive_suggest=False,
                reason_codes=["too_few_messages"],
            )

        # 3. Consecutive declines (count backwards from most recent) ----------
        consecutive_declines = 0
        for suggestion in reversed(recent_suggestions):
            if suggestion.get("outcome") == "declined":
                consecutive_declines += 1
            else:
                break

        # 4. Cooldown if too many consecutive declines ------------------------
        if consecutive_declines >= MAX_CONSECUTIVE_DECLINES:
            cooldown_until = (
                datetime.now(timezone.utc)
                + timedelta(hours=COOLDOWN_HOURS_AFTER_DECLINES)
            ).isoformat()
            return OpportunityResult(
                opportunity_score=0.0,
                allow_proactive_suggest=False,
                reason_codes=["consecutive_declines_cooldown"],
                cooldown_until=cooldown_until,
            )

        # 5. Calculate composite score ----------------------------------------
        es = context.emotional_state
        signal_strength = max(
            es.anxiety,
            es.rumination,
            es.avoidance,
            es.perfectionism,
            es.self_criticism,
            es.symptom_fixation,
        )
        readiness = context.readiness_for_practice
        confidence = context.confidence

        raw_score = (
            0.45 * signal_strength + 0.30 * readiness + 0.25 * confidence
        )
        score = max(0.0, min(1.0, raw_score))

        # 6. Threshold decision -----------------------------------------------
        allow_proactive_suggest = score >= OPPORTUNITY_THRESHOLD

        # 7. Reason codes -----------------------------------------------------
        reason_codes: list[str] = []
        if signal_strength > 0.6:
            reason_codes.append("elevated_emotional_signals")
        if readiness > 0.5:
            reason_codes.append("user_appears_ready")

        return OpportunityResult(
            opportunity_score=score,
            allow_proactive_suggest=allow_proactive_suggest,
            reason_codes=reason_codes,
        )
