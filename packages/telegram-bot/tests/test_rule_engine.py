# tests/test_rule_engine.py
"""Tests for RuleEngine — deterministic practice selection, no blocking."""
import pytest
from wellness_bot.protocol.rules import RuleEngine, PracticeCandidate
from wellness_bot.protocol.types import (
    MaintainingCycle, Readiness, CautionLevel,
)


@pytest.fixture
def engine():
    return RuleEngine()


class TestNoBlockingGates:
    """Core principle: distress and caution never block practices."""

    def test_high_distress_does_not_block(self, engine):
        """High distress should NOT block cognitive practices."""
        candidates = engine.get_eligible(
            distress=9, cycle=MaintainingCycle.WORRY,
            time_budget=10, readiness=Readiness.ACTION,
        )
        ids = {c["id"] for c in candidates}
        # Previously blocked C1/C3 at distress 8+ — now allowed
        assert "C1" in ids
        assert "C2" in ids

    def test_stabilization_boosted_at_high_distress(self, engine):
        """At high distress, stabilization practices get score boost."""
        result = engine.select(
            distress=9, cycle=MaintainingCycle.RUMINATION,
            time_budget=5, readiness=Readiness.ACTION,
            technique_history={},
        )
        # Stabilization practices (A2, A3, U1-U6) should score higher
        assert result.primary.practice_id in ("A2", "A3", "U1", "U2", "U3", "U4", "U5", "U6", "M2")

    def test_caution_does_not_block(self, engine):
        """Caution level should NOT block any practices."""
        candidates = engine.get_eligible(
            distress=5, cycle=MaintainingCycle.AVOIDANCE,
            time_budget=20, readiness=Readiness.ACTION,
            caution=CautionLevel.ELEVATED,
        )
        ids = {c["id"] for c in candidates}
        # Previously blocked at elevated — now allowed
        assert "C3" in ids
        assert "C1" in ids


class TestTimeAndReadinessFilters:
    def test_2min_budget_limited(self, engine):
        candidates = engine.get_eligible(
            distress=5, cycle=MaintainingCycle.RUMINATION,
            time_budget=2, readiness=Readiness.ACTION,
        )
        for c in candidates:
            assert c["dur_min"] <= 2

    def test_precontemplation_limited(self, engine):
        candidates = engine.get_eligible(
            distress=3, cycle=MaintainingCycle.RUMINATION,
            time_budget=10, readiness=Readiness.PRECONTEMPLATION,
        )
        ids = {c["id"] for c in candidates}
        # Only universal + micro at precontemplation
        for pid in ids:
            assert pid in {"M3", "M4", "U1", "U2", "U3", "U4", "U5", "U6"}

    def test_maintenance_unlocks_relapse(self, engine):
        candidates = engine.get_eligible(
            distress=3, cycle=MaintainingCycle.RUMINATION,
            time_budget=20, readiness=Readiness.MAINTENANCE,
        )
        ids = {c["id"] for c in candidates}
        assert "R1" in ids
        assert "R2" in ids
        assert "R3" in ids


class TestCatalogCompleteness:
    def test_catalog_has_30_practices(self, engine):
        """Catalog should have all 30 practices."""
        candidates = engine.get_eligible(
            distress=3, cycle=MaintainingCycle.RUMINATION,
            time_budget=30, readiness=Readiness.MAINTENANCE,
        )
        assert len(candidates) == 30

    def test_insomnia_cycle_maps(self, engine):
        result = engine.select(
            distress=5, cycle=MaintainingCycle.INSOMNIA,
            time_budget=10, readiness=Readiness.ACTION,
            technique_history={},
        )
        assert result.primary.practice_id in ("B5", "A2")


class TestScoring:
    def test_first_line_scores_higher(self, engine):
        result = engine.select(
            distress=5, cycle=MaintainingCycle.RUMINATION,
            time_budget=10, readiness=Readiness.ACTION,
            technique_history={},
        )
        assert result.primary.practice_id in ("A2", "A3", "M2")

    def test_returns_primary_and_backup(self, engine):
        result = engine.select(
            distress=5, cycle=MaintainingCycle.WORRY,
            time_budget=10, readiness=Readiness.ACTION,
            technique_history={},
        )
        assert result.primary is not None
        assert result.backup is not None
        assert result.primary.practice_id != result.backup.practice_id

    def test_score_clamped_0_1(self, engine):
        result = engine.select(
            distress=5, cycle=MaintainingCycle.RUMINATION,
            time_budget=5, readiness=Readiness.ACTION,
            technique_history={"A2": {"times_used": 10, "avg_effectiveness": 0}},
        )
        assert 0.0 <= result.primary.score <= 1.0

    def test_tiebreaker_by_priority_rank(self, engine):
        """When scores are equal, lower priority_rank wins."""
        result = engine.select(
            distress=5, cycle=MaintainingCycle.RUMINATION,
            time_budget=5, readiness=Readiness.ACTION,
            technique_history={},
        )
        # M2 (rank=10), A2 (rank=15), A3 (rank=16) are all first-line for rumination
        # Equal scores → M2 wins by lower priority_rank
        assert result.primary.practice_id == "M2"
