"""Tests for CoachPolicyEngine decision logic.

Key change: crisis/red safety NEVER blocks — agent always helps.
"""

from wellness_bot.coaching.coach_policy import (
    EXPLORE_CONFIDENCE_THRESHOLD,
    SUGGEST_SCORE_THRESHOLD,
    CoachPolicyEngine,
)
from wellness_bot.protocol.types import (
    CoachDecision,
    CoachingDecision,
    ContextState,
    EmotionalState,
    OpportunityResult,
    PracticeCandidateRanked,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _ctx(
    risk: str = "low",
    confidence: float = 0.8,
    readiness: float = 0.6,
    anxiety: float = 0.5,
) -> ContextState:
    return ContextState(
        risk_level=risk,
        emotional_state=EmotionalState(anxiety=anxiety),
        readiness_for_practice=readiness,
        coaching_hypotheses=["thought_loop"],
        confidence=confidence,
        candidate_constraints=[],
    )


def _opp(score: float = 0.8, allow: bool = True) -> OpportunityResult:
    return OpportunityResult(
        opportunity_score=score,
        allow_proactive_suggest=allow,
        reason_codes=[],
    )


def _practices(score: float = 0.8) -> list[PracticeCandidateRanked]:
    return [
        PracticeCandidateRanked(
            practice_id="box_breathing",
            final_score=score,
            confidence=0.9,
            reason_codes=["match_anxiety"],
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCrisisNeverBlocks:
    """Rule 1: crisis/red → agent HELPS (suggest or explore), never just listen."""

    def test_crisis_with_practices_suggests(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(risk="crisis", confidence=0.9, anxiety=0.9),
            opportunity=_opp(score=0.9, allow=True),
            ranked_practices=_practices(score=0.9),
        )
        # Agent helps with a practice even in crisis
        assert result.decision == CoachingDecision.SUGGEST
        assert result.selected_practice_id == "box_breathing"
        assert result.style == "warm_supportive"

    def test_crisis_without_practices_explores(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(risk="crisis", confidence=0.9, anxiety=0.9),
            opportunity=_opp(score=0.9, allow=True),
            ranked_practices=[],
        )
        # No practices available → explore (not just listen)
        assert result.decision == CoachingDecision.EXPLORE
        assert result.style == "warm_supportive"

    def test_red_level_helps(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(risk="red", confidence=0.9, anxiety=0.9),
            opportunity=_opp(score=0.9, allow=True),
            ranked_practices=_practices(score=0.9),
        )
        assert result.decision == CoachingDecision.SUGGEST

    def test_high_risk_helps(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(risk="high", confidence=0.9, anxiety=0.9),
            opportunity=_opp(score=0.9, allow=True),
            ranked_practices=_practices(score=0.9),
        )
        assert result.decision == CoachingDecision.SUGGEST


class TestSuggestWhenOpportunityHighAndPracticeStrong:
    """Rule 5: top practice strong enough -> SUGGEST."""

    def test_suggest_decision(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(confidence=0.8, anxiety=0.6),
            opportunity=_opp(score=0.8, allow=True),
            ranked_practices=_practices(score=0.8),
        )
        assert isinstance(result, CoachDecision)
        assert result.decision == CoachingDecision.SUGGEST
        assert result.selected_practice_id == "box_breathing"
        assert result.must_ask_consent is True
        assert result.style == "warm_directive"

    def test_suggest_with_exact_threshold(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(confidence=0.8, anxiety=0.6),
            opportunity=_opp(score=0.7, allow=True),
            ranked_practices=_practices(score=SUGGEST_SCORE_THRESHOLD),
        )
        assert result.decision == CoachingDecision.SUGGEST


class TestListenWhenOpportunityBlocked:
    """Rule 4: opportunity not allowed -> EXPLORE or LISTEN."""

    def test_listen_when_blocked_low_signal(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(confidence=0.8, anxiety=0.3),
            opportunity=_opp(score=0.2, allow=False),
            ranked_practices=_practices(score=0.8),
        )
        assert result.decision == CoachingDecision.LISTEN

    def test_explore_when_blocked_high_signal(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(confidence=0.8, anxiety=0.6),
            opportunity=_opp(score=0.5, allow=False),
            ranked_practices=_practices(score=0.8),
        )
        assert result.decision == CoachingDecision.EXPLORE


class TestExploreWhenLowConfidence:
    """Rule 3: confidence < 0.5 -> EXPLORE."""

    def test_explore_on_low_confidence(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(confidence=0.3, anxiety=0.6),
            opportunity=_opp(score=0.8, allow=True),
            ranked_practices=_practices(score=0.8),
        )
        assert result.decision == CoachingDecision.EXPLORE
        assert result.style == "warm_curious"

    def test_explore_at_exact_threshold(self) -> None:
        """Confidence exactly at threshold should NOT trigger explore."""
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(confidence=EXPLORE_CONFIDENCE_THRESHOLD, anxiety=0.6),
            opportunity=_opp(score=0.8, allow=True),
            ranked_practices=_practices(score=0.8),
        )
        assert result.decision != CoachingDecision.EXPLORE or result.style != "warm_curious"


class TestAnswerWhenNoSignalNoPractices:
    """Rule 2: no emotional signal + no practices -> ANSWER."""

    def test_answer_no_signal_no_practices(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(confidence=0.8, anxiety=0.1),
            opportunity=_opp(score=0.1, allow=False),
            ranked_practices=[],
        )
        assert result.decision == CoachingDecision.ANSWER
        assert result.style == "direct_helpful"

    def test_answer_all_fields_below_threshold(self) -> None:
        engine = CoachPolicyEngine()
        ctx = _ctx(confidence=0.8, anxiety=0.1)
        ctx.emotional_state.rumination = 0.05
        ctx.emotional_state.avoidance = 0.0
        result = engine.decide(
            context=ctx,
            opportunity=_opp(score=0.1, allow=False),
            ranked_practices=[],
        )
        assert result.decision == CoachingDecision.ANSWER


class TestGuideWhenSignalsPresentButNoStrongMatch:
    """Rule 6: signals present but no strong practice match -> GUIDE."""

    def test_guide_moderate_signal_weak_practice(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(confidence=0.8, anxiety=0.5),
            opportunity=_opp(score=0.7, allow=True),
            ranked_practices=_practices(score=0.4),
        )
        assert result.decision == CoachingDecision.GUIDE
        assert result.style == "warm_curious"


class TestDefaultListen:
    """Rule 7: fallback to LISTEN."""

    def test_default_listen(self) -> None:
        engine = CoachPolicyEngine()
        result = engine.decide(
            context=_ctx(confidence=0.8, anxiety=0.2),
            opportunity=_opp(score=0.5, allow=True),
            ranked_practices=_practices(score=0.3),
        )
        assert result.decision == CoachingDecision.LISTEN
        assert result.style == "warm_supportive"
