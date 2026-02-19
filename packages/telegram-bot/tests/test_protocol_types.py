# tests/test_protocol_types.py
"""Tests for protocol enums and typed contracts."""
import pytest
from wellness_bot.protocol.types import (
    DialogueState,
    SessionType,
    RiskLevel,
    CautionLevel,
    PracticeCategory,
    Readiness,
    MaintainingCycle,
    UIMode,
    ButtonAction,
    FallbackType,
    SessionContext,
    EngineDecision,
    LLMContract,
    ModuleError,
    StateTransition,
    SkippedState,
)


class TestEnums:
    def test_dialogue_states_complete(self):
        states = {s.value for s in DialogueState}
        assert states == {
            "SAFETY_CHECK", "ESCALATION", "INTAKE", "FORMULATION",
            "GOAL_SETTING", "MODULE_SELECT", "PRACTICE",
            "REFLECTION", "REFLECTION_LITE", "HOMEWORK", "SESSION_END",
        }

    def test_session_types_complete(self):
        types = {t.value for t in SessionType}
        assert types == {
            "new_user", "returning", "returning_long_gap",
            "quick_checkin", "crisis", "resume",
        }

    def test_risk_levels(self):
        assert RiskLevel.SAFE.value == "SAFE"
        assert RiskLevel.CRISIS.value == "CRISIS"

    def test_caution_levels(self):
        assert CautionLevel.NONE.value == "none"
        assert CautionLevel.ELEVATED.value == "elevated"

    def test_maintaining_cycles(self):
        cycles = {c.value for c in MaintainingCycle}
        assert "rumination" in cycles
        assert "worry" in cycles
        assert "avoidance" in cycles

    def test_button_actions(self):
        actions = {a.value for a in ButtonAction}
        assert actions == {"next", "fallback", "branch_extended", "branch_help", "backup_practice", "end"}

    def test_fallback_types(self):
        types = {f.value for f in FallbackType}
        assert types == {"user_confused", "cannot_now", "too_hard"}


class TestSessionContext:
    def test_create_context(self):
        ctx = SessionContext(
            user_id=123,
            session_id="sess-001",
            update_id=456,
            risk_level=RiskLevel.SAFE,
            caution_level=CautionLevel.NONE,
            current_state=DialogueState.INTAKE,
            session_type=SessionType.NEW_USER,
        )
        assert ctx.user_id == 123
        assert ctx.risk_level == RiskLevel.SAFE


class TestEngineDecision:
    def test_create_rule_based_decision(self):
        decision = EngineDecision(
            state=DialogueState.PRACTICE,
            action="deliver_step",
            practice_id="A2",
            practice_step=2,
            ui_mode=UIMode.BUTTONS,
            llm_contract=None,
            reason_codes=["rumination_cycle"],
            confidence=None,
            decision_source="rules",
        )
        assert decision.confidence is None
        assert decision.decision_source == "rules"

    def test_create_model_based_decision(self):
        decision = EngineDecision(
            state=DialogueState.SAFETY_CHECK,
            action="classify",
            confidence=0.85,
            decision_source="model",
        )
        assert decision.confidence == 0.85


class TestModuleError:
    def test_recoverable_error(self):
        err = ModuleError(
            module="llm_adapter",
            recoverable=True,
            error_code="VALIDATION_FAIL",
            fallback_response="Как это было для вас? Оцените от 0 до 10.",
        )
        assert err.recoverable is True
