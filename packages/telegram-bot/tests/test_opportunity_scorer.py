"""Tests for proactive opportunity scorer with cooldowns."""

from wellness_bot.coaching.opportunity_scorer import (
    COOLDOWN_HOURS_AFTER_DECLINES,
    MAX_CONSECUTIVE_DECLINES,
    MIN_MESSAGES_BETWEEN_SUGGESTS,
    OPPORTUNITY_THRESHOLD,
    OpportunityScorer,
)
from wellness_bot.protocol.types import ContextState, EmotionalState, OpportunityResult


def _make_context(
    anxiety: float = 0.5,
    rumination: float = 0.5,
    confidence: float = 0.8,
    risk: str = "low",
) -> ContextState:
    return ContextState(
        risk_level=risk,
        emotional_state=EmotionalState(anxiety=anxiety, rumination=rumination),
        readiness_for_practice=0.6,
        coaching_hypotheses=["thought_loop"],
        confidence=confidence,
        candidate_constraints=[],
    )


class TestHighAnxietyScoresHigh:
    """High emotional signals should produce a high score and allow suggest."""

    def test_high_anxiety_allows_suggest(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.9, rumination=0.8, confidence=0.85)
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=5,
        )
        assert isinstance(result, OpportunityResult)
        assert result.opportunity_score > OPPORTUNITY_THRESHOLD
        assert result.allow_proactive_suggest is True
        assert "elevated_emotional_signals" in result.reason_codes

    def test_high_anxiety_score_within_bounds(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.95, rumination=0.95, confidence=0.95)
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=10,
        )
        assert 0.0 <= result.opportunity_score <= 1.0


class TestLowSignalBlocksSuggest:
    """Low emotional signals should produce a low score and block suggest."""

    def test_low_signal_blocks_suggest(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.1, rumination=0.1, confidence=0.3)
        # readiness_for_practice default is 0.6, but low signal + low confidence
        ctx.readiness_for_practice = 0.2
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=5,
        )
        assert result.opportunity_score < OPPORTUNITY_THRESHOLD
        assert result.allow_proactive_suggest is False


class TestCooldownAfterConsecutiveDeclines:
    """Two consecutive declines should trigger a cooldown."""

    def test_two_declines_triggers_cooldown(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.9, rumination=0.8)
        suggestions = [
            {"outcome": "declined"},
            {"outcome": "declined"},
        ]
        result = scorer.score(
            context=ctx,
            recent_suggestions=suggestions,
            messages_since_last_suggest=5,
        )
        assert result.opportunity_score == 0.0
        assert result.allow_proactive_suggest is False
        assert "consecutive_declines_cooldown" in result.reason_codes
        assert result.cooldown_until is not None

    def test_three_declines_also_triggers_cooldown(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context()
        suggestions = [
            {"outcome": "declined"},
            {"outcome": "declined"},
            {"outcome": "declined"},
        ]
        result = scorer.score(
            context=ctx,
            recent_suggestions=suggestions,
            messages_since_last_suggest=5,
        )
        assert result.opportunity_score == 0.0
        assert result.allow_proactive_suggest is False
        assert "consecutive_declines_cooldown" in result.reason_codes


class TestTooFewMessagesBlocksSuggest:
    """Fewer than MIN_MESSAGES_BETWEEN_SUGGESTS messages should block."""

    def test_zero_messages(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.9)
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=0,
        )
        assert result.opportunity_score == 0.0
        assert result.allow_proactive_suggest is False
        assert "too_few_messages" in result.reason_codes

    def test_two_messages(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.9)
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=2,
        )
        assert result.opportunity_score == 0.0
        assert result.allow_proactive_suggest is False
        assert "too_few_messages" in result.reason_codes

    def test_exact_minimum_allows(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.9, rumination=0.8, confidence=0.85)
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=MIN_MESSAGES_BETWEEN_SUGGESTS,
        )
        # Should not be blocked by message count
        assert "too_few_messages" not in result.reason_codes


class TestCrisisBlocksSuggest:
    """Crisis or high risk level should always block."""

    def test_crisis_blocks(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.9, risk="crisis")
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=10,
        )
        assert result.opportunity_score == 0.0
        assert result.allow_proactive_suggest is False
        assert "risk_level_too_high" in result.reason_codes

    def test_high_risk_blocks(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.9, risk="high")
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=10,
        )
        assert result.opportunity_score == 0.0
        assert result.allow_proactive_suggest is False
        assert "risk_level_too_high" in result.reason_codes


class TestAcceptedResetsDeclineCount:
    """An accepted suggestion between declines should reset the count."""

    def test_accepted_between_declines_resets(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.9, rumination=0.8, confidence=0.85)
        # One decline, then accepted, then one decline = 1 consecutive decline
        suggestions = [
            {"outcome": "declined"},
            {"outcome": "accepted"},
            {"outcome": "declined"},
        ]
        result = scorer.score(
            context=ctx,
            recent_suggestions=suggestions,
            messages_since_last_suggest=5,
        )
        # Only 1 consecutive decline from the end, so no cooldown
        assert "consecutive_declines_cooldown" not in result.reason_codes
        assert result.allow_proactive_suggest is True
        assert result.opportunity_score > 0.0

    def test_accepted_at_end_means_zero_declines(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.9, rumination=0.8, confidence=0.85)
        suggestions = [
            {"outcome": "declined"},
            {"outcome": "declined"},
            {"outcome": "accepted"},
        ]
        result = scorer.score(
            context=ctx,
            recent_suggestions=suggestions,
            messages_since_last_suggest=5,
        )
        assert "consecutive_declines_cooldown" not in result.reason_codes
        assert result.allow_proactive_suggest is True


class TestReasonCodes:
    """Verify reason codes are correctly populated."""

    def test_elevated_emotional_signals_code(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.7, rumination=0.3, confidence=0.8)
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=5,
        )
        assert "elevated_emotional_signals" in result.reason_codes

    def test_user_appears_ready_code(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.7, confidence=0.8)
        ctx.readiness_for_practice = 0.7
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=5,
        )
        assert "user_appears_ready" in result.reason_codes

    def test_no_elevated_signal_code_when_low(self) -> None:
        scorer = OpportunityScorer()
        ctx = _make_context(anxiety=0.3, rumination=0.3, confidence=0.5)
        ctx.readiness_for_practice = 0.3
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=5,
        )
        assert "elevated_emotional_signals" not in result.reason_codes


class TestScoreFormula:
    """Verify the weighted score calculation."""

    def test_known_score_value(self) -> None:
        scorer = OpportunityScorer()
        # signal_strength = max(0.8, 0.6, 0, 0, 0, 0) = 0.8
        # readiness = 0.6
        # confidence = 0.7
        # score = 0.45*0.8 + 0.30*0.6 + 0.25*0.7 = 0.36 + 0.18 + 0.175 = 0.715
        ctx = _make_context(anxiety=0.8, rumination=0.6, confidence=0.7)
        ctx.readiness_for_practice = 0.6
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=5,
        )
        assert abs(result.opportunity_score - 0.715) < 0.001

    def test_score_clamped_to_one(self) -> None:
        scorer = OpportunityScorer()
        # Even with max values, score should not exceed 1.0
        ctx = _make_context(anxiety=1.0, rumination=1.0, confidence=1.0)
        ctx.readiness_for_practice = 1.0
        result = scorer.score(
            context=ctx,
            recent_suggestions=[],
            messages_since_last_suggest=5,
        )
        assert result.opportunity_score <= 1.0
        # 0.45*1.0 + 0.30*1.0 + 0.25*1.0 = 1.0
        assert abs(result.opportunity_score - 1.0) < 0.001
