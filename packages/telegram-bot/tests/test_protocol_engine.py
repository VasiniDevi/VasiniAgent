# tests/test_protocol_engine.py
"""Tests for ProtocolEngine FSM."""
import pytest
from wellness_bot.protocol.engine import ProtocolEngine
from wellness_bot.protocol.types import DialogueState, SessionType, RiskLevel


class TestAllowedTransitions:
    @pytest.fixture
    def engine(self):
        return ProtocolEngine()

    def test_safety_to_intake(self, engine):
        assert engine.is_transition_allowed(DialogueState.SAFETY_CHECK, DialogueState.INTAKE)

    def test_safety_to_escalation(self, engine):
        assert engine.is_transition_allowed(DialogueState.SAFETY_CHECK, DialogueState.ESCALATION)

    def test_safety_to_formulation(self, engine):
        assert engine.is_transition_allowed(DialogueState.SAFETY_CHECK, DialogueState.FORMULATION)

    def test_intake_to_formulation(self, engine):
        assert engine.is_transition_allowed(DialogueState.INTAKE, DialogueState.FORMULATION)

    def test_intake_to_goal_disallowed(self, engine):
        assert not engine.is_transition_allowed(DialogueState.INTAKE, DialogueState.GOAL_SETTING)

    def test_escalation_only_to_session_end(self, engine):
        assert engine.is_transition_allowed(DialogueState.ESCALATION, DialogueState.SESSION_END)
        assert not engine.is_transition_allowed(DialogueState.ESCALATION, DialogueState.INTAKE)

    def test_any_to_safety_check(self, engine):
        """Re-entry trigger: any state can go to SAFETY_CHECK."""
        for state in DialogueState:
            if state not in (DialogueState.SAFETY_CHECK, DialogueState.SESSION_END):
                assert engine.is_transition_allowed(state, DialogueState.SAFETY_CHECK)

    def test_any_to_session_end(self, engine):
        """user_stop / timeout: any state can go to SESSION_END."""
        for state in DialogueState:
            if state != DialogueState.SESSION_END:
                assert engine.is_transition_allowed(state, DialogueState.SESSION_END)


class TestSessionTypeClassifier:
    @pytest.fixture
    def engine(self):
        return ProtocolEngine()

    def test_new_user(self, engine):
        st = engine.classify_session(profile=None, last_session_days=None, has_resumable=False)
        assert st == SessionType.NEW_USER

    def test_returning(self, engine):
        st = engine.classify_session(profile={"user_id": 1}, last_session_days=5, has_resumable=False)
        assert st == SessionType.RETURNING

    def test_returning_long_gap(self, engine):
        st = engine.classify_session(profile={"user_id": 1}, last_session_days=30, has_resumable=False)
        assert st == SessionType.RETURNING_LONG_GAP

    def test_resume(self, engine):
        st = engine.classify_session(profile={"user_id": 1}, last_session_days=1, has_resumable=True)
        assert st == SessionType.RESUME


class TestNextState:
    @pytest.fixture
    def engine(self):
        return ProtocolEngine()

    def test_new_user_after_safety(self, engine):
        state = engine.next_state_after_safety(
            session_type=SessionType.NEW_USER,
            risk_level=RiskLevel.SAFE,
        )
        assert state == DialogueState.INTAKE

    def test_returning_after_safety(self, engine):
        state = engine.next_state_after_safety(
            session_type=SessionType.RETURNING,
            risk_level=RiskLevel.SAFE,
        )
        assert state == DialogueState.FORMULATION

    def test_crisis_after_safety(self, engine):
        state = engine.next_state_after_safety(
            session_type=SessionType.NEW_USER,
            risk_level=RiskLevel.CRISIS,
        )
        assert state == DialogueState.ESCALATION

    def test_resume_after_safety(self, engine):
        state = engine.next_state_after_safety(
            session_type=SessionType.RESUME,
            risk_level=RiskLevel.SAFE,
        )
        assert state == DialogueState.PRACTICE

    def test_returning_long_gap_goes_to_intake(self, engine):
        state = engine.next_state_after_safety(
            session_type=SessionType.RETURNING_LONG_GAP,
            risk_level=RiskLevel.SAFE,
        )
        assert state == DialogueState.INTAKE
