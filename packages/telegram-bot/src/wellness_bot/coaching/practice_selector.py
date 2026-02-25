"""Practice selector — ranks practices from catalog using weighted scoring.

Step 5 in the coaching pipeline.  Applies a multi-factor weighted scoring
formula to each practice in the active catalog, filters out contraindicated
entries, applies overuse and decline penalties, and returns the top-k
candidates sorted by final score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wellness_bot.protocol.types import ContextState, PracticeCandidateRanked

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

W_STATE_MATCH: float = 0.35
W_HISTORICAL: float = 0.25
W_READINESS: float = 0.15
W_DURATION: float = 0.15
W_NOVELTY: float = 0.10

# ---------------------------------------------------------------------------
# Penalty parameters
# ---------------------------------------------------------------------------

OVERUSE_THRESHOLD_7D: int = 2
OVERUSE_PENALTY_PER_USE: float = 0.08
DECLINE_PENALTY: float = 0.12

# ---------------------------------------------------------------------------
# Target-to-field mapping
# ---------------------------------------------------------------------------

_TARGET_FIELD_MAP: dict[str, str] = {
    "anxiety": "anxiety",
    "rumination": "rumination",
    "avoidance": "avoidance",
    "perfectionism": "perfectionism",
    "self_criticism": "self_criticism",
    "symptom_fixation": "symptom_fixation",
}


# ---------------------------------------------------------------------------
# Catalog entry dataclass
# ---------------------------------------------------------------------------


@dataclass
class PracticeCatalogEntry:
    """A single practice in the catalog."""

    id: str
    slug: str
    title: str
    targets: list[str]
    contraindications: list[str]
    duration_min: int
    duration_max: int | None = None
    active: bool = True


# ---------------------------------------------------------------------------
# PracticeSelector
# ---------------------------------------------------------------------------


class PracticeSelector:
    """Rank practices from the catalog using a weighted scoring formula.

    Parameters
    ----------
    catalog:
        Full list of ``PracticeCatalogEntry`` objects.  Only active entries
        are retained for selection.
    """

    def __init__(self, catalog: list[PracticeCatalogEntry]) -> None:
        self._catalog = [entry for entry in catalog if entry.active]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select(
        self,
        context: ContextState,
        opportunity_score: float,
        user_history: dict[str, dict[str, Any]],
        top_k: int = 3,
        contraindications: list[str] | None = None,
    ) -> list[PracticeCandidateRanked]:
        """Score, rank, and return the top-k practice candidates.

        Parameters
        ----------
        context:
            Current conversation context (risk, emotional state, readiness).
        opportunity_score:
            Opportunity score from the OpportunityScorer (0-1).
        user_history:
            Per-practice usage data keyed by practice ID.  Each value is a
            dict with ``times_used_7d``, ``avg_effectiveness``, and
            ``last_declined``.
        top_k:
            Maximum number of candidates to return.
        contraindications:
            Hard-filter list — any practice whose ``contraindications``
            overlap with this list is excluded.

        Returns
        -------
        list[PracticeCandidateRanked]
            Up to *top_k* candidates sorted by ``final_score`` descending.
        """
        contra_set = set(contraindications) if contraindications else set()
        emotional_state = context.emotional_state

        # Compute the max emotional signal for duration_fit calculation
        max_signal = max(
            emotional_state.anxiety,
            emotional_state.rumination,
            emotional_state.avoidance,
            emotional_state.perfectionism,
            emotional_state.self_criticism,
            emotional_state.symptom_fixation,
        )

        scored: list[PracticeCandidateRanked] = []

        for entry in self._catalog:
            # 1. Hard filter: contraindications
            if contra_set and contra_set.intersection(entry.contraindications):
                continue

            # 2. Retrieve per-practice history
            history = user_history.get(entry.id, {})
            times_used_7d: int = history.get("times_used_7d", 0)
            avg_effectiveness: float = history.get("avg_effectiveness", 0.5)
            last_declined: bool = history.get("last_declined", False)

            # 3. Component scores
            state_match = self._calc_state_match(entry.targets, emotional_state)
            historical = avg_effectiveness
            readiness_fit = context.readiness_for_practice

            # duration_fit
            if max_signal > 0.7:
                duration_fit = 1.0 if entry.duration_min <= 10 else 0.4
            else:
                duration_fit = 0.7

            # novelty
            novelty = max(0.0, 1.0 - times_used_7d * 0.2)

            # 4. Weighted base score
            base_score = (
                W_STATE_MATCH * state_match
                + W_HISTORICAL * historical
                + W_READINESS * readiness_fit
                + W_DURATION * duration_fit
                + W_NOVELTY * novelty
            )

            # 5. Penalties
            overuse_penalty = max(0, times_used_7d - OVERUSE_THRESHOLD_7D) * OVERUSE_PENALTY_PER_USE
            decline_penalty = DECLINE_PENALTY if last_declined else 0.0

            # 6. Final score (clamped 0-1)
            final_score = max(0.0, min(1.0, base_score - overuse_penalty - decline_penalty))

            # 7. Reason codes
            reason_codes: list[str] = []
            if state_match > 0.5:
                reason_codes.append(f"matches_{emotional_state.dominant}")
            if historical > 0.6:
                reason_codes.append("worked_before")
            if entry.duration_min <= 5:
                reason_codes.append("short_duration")

            scored.append(
                PracticeCandidateRanked(
                    practice_id=entry.id,
                    final_score=round(final_score, 6),
                    confidence=context.confidence,
                    reason_codes=reason_codes,
                )
            )

        # 8. Sort descending by final_score, return top_k
        scored.sort(key=lambda c: c.final_score, reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_state_match(
        targets: list[str],
        emotional_state: Any,
    ) -> float:
        """Calculate how well a practice's targets match the emotional state.

        For each target that maps to an emotional_state field, the
        corresponding field value is collected.  The maximum is returned.
        If no target maps, a default of 0.3 is used.
        """
        values: list[float] = []
        for target in targets:
            field_name = _TARGET_FIELD_MAP.get(target)
            if field_name is not None:
                values.append(getattr(emotional_state, field_name, 0.0))
        return max(values) if values else 0.3
