"""Tests for new type definitions: 2-level FSM enums and coaching pipeline dataclasses."""
from __future__ import annotations

import pytest

from wellness_bot.protocol.types import (
    CoachDecision,
    CoachingDecision,
    ConsentStatus,
    ContextState,
    ConversationState,
    EmotionalState,
    OpportunityResult,
    PracticeCandidateRanked,
    PracticeState,
)


# ---------------------------------------------------------------------------
# Enum value tests
# ---------------------------------------------------------------------------

class TestConversationState:
    def test_all_values_exist(self):
        expected = [
            "FREE_CHAT",
            "EXPLORE",
            "PRACTICE_OFFERED",
            "PRACTICE_ACTIVE",
            "PRACTICE_PAUSED",
            "FOLLOW_UP",
            "CRISIS",
        ]
        for name in expected:
            member = ConversationState[name]
            assert member.value == name

    def test_is_str_enum(self):
        assert isinstance(ConversationState.FREE_CHAT, str)


class TestPracticeState:
    def test_all_values_exist(self):
        expected = [
            "CONSENT",
            "BASELINE",
            "STEP",
            "CHECKPOINT",
            "ADAPT",
            "WRAP_UP",
            "FOLLOW_UP",
        ]
        for name in expected:
            member = PracticeState[name]
            assert member.value == name

    def test_is_str_enum(self):
        assert isinstance(PracticeState.CONSENT, str)


class TestCoachingDecision:
    def test_all_values_exist(self):
        expected = ["LISTEN", "EXPLORE", "SUGGEST", "GUIDE", "ANSWER"]
        for name in expected:
            member = CoachingDecision[name]
            assert member.value == name

    def test_is_str_enum(self):
        assert isinstance(CoachingDecision.LISTEN, str)


class TestConsentStatus:
    def test_all_values_exist(self):
        expected = ["PENDING", "ACCEPTED", "DECLINED"]
        for name in expected:
            member = ConsentStatus[name]
            assert member.value == name

    def test_is_str_enum(self):
        assert isinstance(ConsentStatus.PENDING, str)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestEmotionalState:
    def test_defaults_all_zero(self):
        es = EmotionalState()
        assert es.anxiety == 0.0
        assert es.rumination == 0.0
        assert es.avoidance == 0.0
        assert es.perfectionism == 0.0
        assert es.self_criticism == 0.0
        assert es.symptom_fixation == 0.0

    def test_dominant_single_max(self):
        es = EmotionalState(rumination=0.9, anxiety=0.3)
        assert es.dominant == "rumination"

    def test_dominant_returns_first_when_tie(self):
        """When multiple fields share the max, dominant returns the first one in field order."""
        es = EmotionalState(anxiety=0.5, avoidance=0.5)
        # anxiety comes first in field order
        assert es.dominant == "anxiety"

    def test_dominant_all_zero(self):
        es = EmotionalState()
        # When all zero, should still return a field name (first in order)
        assert es.dominant == "anxiety"

    def test_custom_values(self):
        es = EmotionalState(
            anxiety=0.1,
            rumination=0.2,
            avoidance=0.3,
            perfectionism=0.4,
            self_criticism=0.5,
            symptom_fixation=0.6,
        )
        assert es.dominant == "symptom_fixation"


class TestContextState:
    def test_creation(self):
        es = EmotionalState(anxiety=0.7)
        ctx = ContextState(
            risk_level="SAFE",
            emotional_state=es,
            readiness_for_practice=0.6,
            coaching_hypotheses=["rumination_loop"],
            confidence=0.8,
            candidate_constraints=["no_exposure"],
        )
        assert ctx.risk_level == "SAFE"
        assert ctx.emotional_state.anxiety == 0.7
        assert ctx.readiness_for_practice == 0.6
        assert ctx.coaching_hypotheses == ["rumination_loop"]
        assert ctx.confidence == 0.8
        assert ctx.candidate_constraints == ["no_exposure"]


class TestOpportunityResult:
    def test_creation_minimal(self):
        result = OpportunityResult(
            opportunity_score=0.75,
            allow_proactive_suggest=True,
            reason_codes=["emotional_window"],
        )
        assert result.opportunity_score == 0.75
        assert result.allow_proactive_suggest is True
        assert result.reason_codes == ["emotional_window"]
        assert result.cooldown_until is None

    def test_creation_with_cooldown(self):
        result = OpportunityResult(
            opportunity_score=0.2,
            allow_proactive_suggest=False,
            reason_codes=["cooldown_active"],
            cooldown_until="2026-02-25T12:00:00",
        )
        assert result.cooldown_until == "2026-02-25T12:00:00"


class TestPracticeCandidateRanked:
    def test_creation_minimal(self):
        candidate = PracticeCandidateRanked(
            practice_id="thought_record_v1",
            final_score=0.85,
            confidence=0.9,
            reason_codes=["matches_rumination"],
        )
        assert candidate.practice_id == "thought_record_v1"
        assert candidate.final_score == 0.85
        assert candidate.confidence == 0.9
        assert candidate.reason_codes == ["matches_rumination"]
        assert candidate.blocked_by is None
        assert candidate.alternative_ids is None

    def test_creation_with_optionals(self):
        candidate = PracticeCandidateRanked(
            practice_id="exposure_v1",
            final_score=0.4,
            confidence=0.6,
            reason_codes=["partial_match"],
            blocked_by=["high_anxiety"],
            alternative_ids=["grounding_v1"],
        )
        assert candidate.blocked_by == ["high_anxiety"]
        assert candidate.alternative_ids == ["grounding_v1"]


class TestCoachDecision:
    def test_creation_defaults(self):
        cd = CoachDecision(decision=CoachingDecision.LISTEN)
        assert cd.decision == CoachingDecision.LISTEN
        assert cd.selected_practice_id is None
        assert cd.style == "warm_supportive"
        assert cd.must_ask_consent is False

    def test_creation_full(self):
        cd = CoachDecision(
            decision=CoachingDecision.GUIDE,
            selected_practice_id="thought_record_v1",
            style="gentle_directive",
            must_ask_consent=True,
        )
        assert cd.decision == CoachingDecision.GUIDE
        assert cd.selected_practice_id == "thought_record_v1"
        assert cd.style == "gentle_directive"
        assert cd.must_ask_consent is True
