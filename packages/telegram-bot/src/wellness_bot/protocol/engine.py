"""ProtocolEngine — Hybrid FSM with allowed transitions whitelist."""
from __future__ import annotations

from wellness_bot.protocol.types import DialogueState, SessionType, RiskLevel


# Allowed transitions whitelist (design doc Section 2)
_ALLOWED: dict[DialogueState, set[DialogueState]] = {
    DialogueState.SAFETY_CHECK: {
        DialogueState.ESCALATION,
        DialogueState.INTAKE,
        DialogueState.FORMULATION,
        DialogueState.PRACTICE,  # resume, guarded
    },
    DialogueState.ESCALATION: {DialogueState.SESSION_END},
    DialogueState.INTAKE: {DialogueState.FORMULATION},
    DialogueState.FORMULATION: {DialogueState.GOAL_SETTING},
    DialogueState.GOAL_SETTING: {DialogueState.MODULE_SELECT},
    DialogueState.MODULE_SELECT: {DialogueState.PRACTICE},
    DialogueState.PRACTICE: {DialogueState.REFLECTION, DialogueState.REFLECTION_LITE},
    DialogueState.REFLECTION: {DialogueState.HOMEWORK},
    DialogueState.REFLECTION_LITE: {DialogueState.HOMEWORK},
    DialogueState.HOMEWORK: {DialogueState.SESSION_END},
    DialogueState.SESSION_END: set(),
}

# Re-entry: any state (except SESSION_END) can go to SAFETY_CHECK or SESSION_END
_GLOBAL_TARGETS = {DialogueState.SAFETY_CHECK, DialogueState.SESSION_END}


class ProtocolEngine:
    def is_transition_allowed(self, from_state: DialogueState, to_state: DialogueState) -> bool:
        if from_state == DialogueState.SESSION_END:
            return False
        if to_state in _GLOBAL_TARGETS:
            return True
        return to_state in _ALLOWED.get(from_state, set())

    def classify_session(
        self,
        profile: dict | None,
        last_session_days: int | None,
        has_resumable: bool,
    ) -> SessionType:
        if profile is None:
            return SessionType.NEW_USER
        if has_resumable:
            return SessionType.RESUME
        if last_session_days is not None and last_session_days >= 14:
            return SessionType.RETURNING_LONG_GAP
        return SessionType.RETURNING

    def next_state_after_safety(
        self,
        session_type: SessionType,
        risk_level: RiskLevel,
    ) -> DialogueState:
        if risk_level == RiskLevel.CRISIS:
            return DialogueState.ESCALATION
        if session_type == SessionType.NEW_USER:
            return DialogueState.INTAKE
        if session_type == SessionType.RETURNING_LONG_GAP:
            return DialogueState.INTAKE  # short re-intake
        if session_type == SessionType.RESUME:
            return DialogueState.PRACTICE
        # RETURNING, QUICK_CHECKIN
        return DialogueState.FORMULATION
