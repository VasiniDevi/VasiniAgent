# tests/test_rule_engine.py
"""Tests for RuleEngine — deterministic practice selection."""
import pytest
from wellness_bot.protocol.rules import RuleEngine, PracticeCandidate
from wellness_bot.protocol.types import (
    MaintainingCycle, Readiness, CautionLevel,
)


@pytest.fixture
def engine():
    return RuleEngine()


class TestHardFilter:
    def test_high_distress_blocks_cognitive(self, engine):
        candidates = engine.get_eligible(
            distress=9, cycle=MaintainingCycle.WORRY,
            time_budget=5, readiness=Readiness.ACTION,
            caution=CautionLevel.NONE,
        )
        ids = {c["id"] for c in candidates}
        assert "C1" not in ids  # Socratic blocked at 8+
        assert "C3" not in ids  # experiment blocked
        assert "A3" in ids or "A2" in ids  # stabilization allowed

    def test_low_distress_allows_all(self, engine):
        candidates = engine.get_eligible(
            distress=2, cycle=MaintainingCycle.AVOIDANCE,
            time_budget=20, readiness=Readiness.ACTION,
            caution=CautionLevel.NONE,
        )
        ids = {c["id"] for c in candidates}
        assert "C3" in ids  # experiment allowed
        assert "C1" in ids  # Socratic allowed

    def test_2min_budget_limited(self, engine):
        candidates = engine.get_eligible(
            distress=5, cycle=MaintainingCycle.RUMINATION,
            time_budget=2, readiness=Readiness.ACTION,
            caution=CautionLevel.NONE,
        )
        ids = {c["id"] for c in candidates}
        # All practices with dur_min <= 2 pass the time gate
        assert ids.issubset({"U2", "M3", "A2", "A3", "A6", "M2"})
        # Long practices excluded
        assert "C3" not in ids
        assert "A1" not in ids

    def test_caution_elevated_blocks_exposure(self, engine):
        candidates = engine.get_eligible(
            distress=5, cycle=MaintainingCycle.AVOIDANCE,
            time_budget=20, readiness=Readiness.ACTION,
            caution=CautionLevel.ELEVATED,
        )
        ids = {c["id"] for c in candidates}
        assert "C3" not in ids  # experiment blocked at elevated
        assert "C1" not in ids  # Socratic (confrontational) blocked

    def test_precontemplation_only_basics(self, engine):
        candidates = engine.get_eligible(
            distress=3, cycle=MaintainingCycle.RUMINATION,
            time_budget=10, readiness=Readiness.PRECONTEMPLATION,
            caution=CautionLevel.NONE,
        )
        ids = {c["id"] for c in candidates}
        assert ids.issubset({"M3", "U2"})


class TestScoring:
    def test_first_line_scores_higher(self, engine):
        candidates = engine.select(
            distress=5, cycle=MaintainingCycle.RUMINATION,
            time_budget=10, readiness=Readiness.ACTION,
            caution=CautionLevel.NONE,
            technique_history={},
        )
        # A2 (first-line for rumination) should score higher than C1 (not matched)
        assert candidates.primary.practice_id in ("A2", "A3", "M2")

    def test_returns_primary_and_backup(self, engine):
        result = engine.select(
            distress=5, cycle=MaintainingCycle.WORRY,
            time_budget=10, readiness=Readiness.ACTION,
            caution=CautionLevel.NONE,
            technique_history={},
        )
        assert result.primary is not None
        assert result.backup is not None
        assert result.primary.practice_id != result.backup.practice_id

    def test_score_clamped_0_1(self, engine):
        result = engine.select(
            distress=5, cycle=MaintainingCycle.RUMINATION,
            time_budget=5, readiness=Readiness.ACTION,
            caution=CautionLevel.NONE,
            technique_history={"A2": {"times_used": 10, "avg_effectiveness": 0}},
        )
        assert 0.0 <= result.primary.score <= 1.0

    def test_tiebreaker_by_priority_rank(self, engine):
        """When scores are equal, lower priority_rank wins."""
        result = engine.select(
            distress=5, cycle=MaintainingCycle.RUMINATION,
            time_budget=5, readiness=Readiness.ACTION,
            caution=CautionLevel.NONE,
            technique_history={},
        )
        # M2 (rank=10), A2 (rank=15), A3 (rank=16) are all first-line for rumination
        # Equal scores → M2 wins by lower priority_rank
        assert result.primary.practice_id == "M2"
