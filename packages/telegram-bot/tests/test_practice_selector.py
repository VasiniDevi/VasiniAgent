"""Tests for PracticeSelector — weighted scoring and ranking of practices."""

from __future__ import annotations

import pytest

from wellness_bot.coaching.practice_selector import PracticeCatalogEntry, PracticeSelector
from wellness_bot.protocol.types import ContextState, EmotionalState, PracticeCandidateRanked

# ---------------------------------------------------------------------------
# Sample catalog entries
# ---------------------------------------------------------------------------

GROUNDING = PracticeCatalogEntry(
    id="U2",
    slug="grounding",
    title="Grounding Exercise",
    targets=["anxiety"],
    contraindications=[],
    duration_min=5,
)

SOCRATIC = PracticeCatalogEntry(
    id="C1",
    slug="socratic",
    title="Socratic Questioning",
    targets=["rumination"],
    contraindications=[],
    duration_min=8,
)

BEHAVIORAL_EXPERIMENT = PracticeCatalogEntry(
    id="C3",
    slug="behavioral_experiment",
    title="Behavioral Experiment",
    targets=["avoidance"],
    contraindications=["high_distress"],
    duration_min=15,
)

CATALOG = [GROUNDING, SOCRATIC, BEHAVIORAL_EXPERIMENT]


def _make_context(
    *,
    anxiety: float = 0.0,
    rumination: float = 0.0,
    avoidance: float = 0.0,
    readiness: float = 0.5,
) -> ContextState:
    """Build a ContextState with specified emotional values."""
    return ContextState(
        risk_level="low",
        emotional_state=EmotionalState(
            anxiety=anxiety,
            rumination=rumination,
            avoidance=avoidance,
        ),
        readiness_for_practice=readiness,
        coaching_hypotheses=[],
        confidence=0.8,
        candidate_constraints=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPracticeSelector:
    """Core tests for the weighted practice selector."""

    def test_returns_ranked_list(self) -> None:
        """select() returns a list of PracticeCandidateRanked."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(anxiety=0.5)
        results = selector.select(context, opportunity_score=0.7, user_history={})
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, PracticeCandidateRanked) for r in results)

    def test_high_anxiety_ranks_grounding_first(self) -> None:
        """When anxiety is dominant, grounding (targets=anxiety) should rank first."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(anxiety=0.9)
        results = selector.select(context, opportunity_score=0.7, user_history={})
        assert results[0].practice_id == "U2"

    def test_high_rumination_ranks_socratic_first(self) -> None:
        """When rumination is dominant, socratic (targets=rumination) should rank first."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(rumination=0.9)
        results = selector.select(context, opportunity_score=0.7, user_history={})
        assert results[0].practice_id == "C1"

    def test_contraindicated_practice_excluded(self) -> None:
        """Practices whose contraindications overlap the supplied list are excluded."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(avoidance=0.9)
        results = selector.select(
            context,
            opportunity_score=0.7,
            user_history={},
            contraindications=["high_distress"],
        )
        ids = [r.practice_id for r in results]
        assert "C3" not in ids

    def test_overuse_penalty_applied(self) -> None:
        """A practice used many times in 7 days should receive a lower score."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(anxiety=0.8)

        # No history — baseline
        results_fresh = selector.select(context, opportunity_score=0.7, user_history={})
        score_fresh = next(r.final_score for r in results_fresh if r.practice_id == "U2")

        # Heavy history — overuse
        history = {"U2": {"times_used_7d": 6, "avg_effectiveness": 0.5, "last_declined": False}}
        results_overuse = selector.select(context, opportunity_score=0.7, user_history=history)
        score_overuse = next(r.final_score for r in results_overuse if r.practice_id == "U2")

        assert score_overuse < score_fresh

    def test_empty_catalog_returns_empty(self) -> None:
        """An empty catalog should produce an empty result list."""
        selector = PracticeSelector([])
        context = _make_context(anxiety=0.5)
        results = selector.select(context, opportunity_score=0.7, user_history={})
        assert results == []

    def test_results_sorted_by_score_desc(self) -> None:
        """Returned results are in descending order of final_score."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(anxiety=0.6, rumination=0.4, avoidance=0.2)
        results = selector.select(context, opportunity_score=0.7, user_history={})
        scores = [r.final_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_inactive_entry_filtered(self) -> None:
        """Inactive catalog entries are excluded from selection."""
        inactive = PracticeCatalogEntry(
            id="X1",
            slug="inactive",
            title="Inactive Practice",
            targets=["anxiety"],
            contraindications=[],
            duration_min=5,
            active=False,
        )
        selector = PracticeSelector(CATALOG + [inactive])
        context = _make_context(anxiety=0.9)
        results = selector.select(context, opportunity_score=0.7, user_history={})
        ids = [r.practice_id for r in results]
        assert "X1" not in ids

    def test_decline_penalty_applied(self) -> None:
        """A practice that was last declined should receive a lower score."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(anxiety=0.8)

        history_ok = {"U2": {"times_used_7d": 0, "avg_effectiveness": 0.5, "last_declined": False}}
        results_ok = selector.select(context, opportunity_score=0.7, user_history=history_ok)
        score_ok = next(r.final_score for r in results_ok if r.practice_id == "U2")

        history_declined = {"U2": {"times_used_7d": 0, "avg_effectiveness": 0.5, "last_declined": True}}
        results_declined = selector.select(context, opportunity_score=0.7, user_history=history_declined)
        score_declined = next(r.final_score for r in results_declined if r.practice_id == "U2")

        assert score_declined < score_ok

    def test_reason_codes_include_matches_dominant(self) -> None:
        """When state_match > 0.5 the reason codes should contain 'matches_{dominant}'."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(anxiety=0.9)
        results = selector.select(context, opportunity_score=0.7, user_history={})
        grounding = next(r for r in results if r.practice_id == "U2")
        assert any(code.startswith("matches_") for code in grounding.reason_codes)

    def test_reason_codes_include_short_duration(self) -> None:
        """Practices with duration_min <= 5 should get 'short_duration' reason code."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(anxiety=0.5)
        results = selector.select(context, opportunity_score=0.7, user_history={})
        grounding = next(r for r in results if r.practice_id == "U2")
        assert "short_duration" in grounding.reason_codes

    def test_reason_codes_include_worked_before(self) -> None:
        """Practices with avg_effectiveness > 0.6 should get 'worked_before' reason code."""
        selector = PracticeSelector(CATALOG)
        context = _make_context(anxiety=0.7)
        history = {"U2": {"times_used_7d": 1, "avg_effectiveness": 0.8, "last_declined": False}}
        results = selector.select(context, opportunity_score=0.7, user_history=history)
        grounding = next(r for r in results if r.practice_id == "U2")
        assert "worked_before" in grounding.reason_codes
