"""Enums and typed contracts for the protocol engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal


class DialogueState(str, Enum):
    SAFETY_CHECK = "SAFETY_CHECK"
    ESCALATION = "ESCALATION"
    INTAKE = "INTAKE"
    FORMULATION = "FORMULATION"
    GOAL_SETTING = "GOAL_SETTING"
    MODULE_SELECT = "MODULE_SELECT"
    PRACTICE = "PRACTICE"
    REFLECTION = "REFLECTION"
    REFLECTION_LITE = "REFLECTION_LITE"
    HOMEWORK = "HOMEWORK"
    SESSION_END = "SESSION_END"


class SessionType(str, Enum):
    NEW_USER = "new_user"
    RETURNING = "returning"
    RETURNING_LONG_GAP = "returning_long_gap"
    QUICK_CHECKIN = "quick_checkin"
    CRISIS = "crisis"
    RESUME = "resume"


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    CAUTION_MILD = "CAUTION_MILD"
    CAUTION_ELEVATED = "CAUTION_ELEVATED"
    CRISIS = "CRISIS"


class CautionLevel(str, Enum):
    NONE = "none"
    MILD = "mild"
    ELEVATED = "elevated"


class PracticeCategory(str, Enum):
    MONITORING = "monitoring"
    ATTENTION = "attention"
    COGNITIVE = "cognitive"
    BEHAVIORAL = "behavioral"
    MICRO = "micro"


class Readiness(str, Enum):
    PRECONTEMPLATION = "precontemplation"
    CONTEMPLATION = "contemplation"
    ACTION = "action"
    MAINTENANCE = "maintenance"


class MaintainingCycle(str, Enum):
    RUMINATION = "rumination"
    WORRY = "worry"
    AVOIDANCE = "avoidance"
    PERFECTIONISM = "perfectionism"
    SELF_CRITICISM = "self_criticism"
    SYMPTOM_FIXATION = "symptom_fixation"


class UIMode(str, Enum):
    TEXT = "text"
    BUTTONS = "buttons"
    TIMER = "timer"
    TEXT_INPUT = "text_input"


class ButtonAction(str, Enum):
    NEXT = "next"
    FALLBACK = "fallback"
    BRANCH_EXTENDED = "branch_extended"
    BRANCH_HELP = "branch_help"
    BACKUP_PRACTICE = "backup_practice"
    END = "end"


class FallbackType(str, Enum):
    USER_CONFUSED = "user_confused"
    CANNOT_NOW = "cannot_now"
    TOO_HARD = "too_hard"


@dataclass
class SessionContext:
    user_id: int
    session_id: str
    update_id: int
    risk_level: RiskLevel
    caution_level: CautionLevel
    current_state: DialogueState
    session_type: SessionType
    distress_level: int | None = None
    maintaining_cycle: MaintainingCycle | None = None
    time_budget: int | None = None
    readiness: Readiness | None = None
    session_number: int = 1


@dataclass
class LLMContract:
    dialogue_state: str
    generation_task: str
    instruction: str
    persona_summary: str
    user_summary: str
    recent_messages: list[dict] = field(default_factory=list)
    max_messages: int = 2
    max_chars_per_message: int = 500
    language: str = "ru"
    must_include: list[str] = field(default_factory=list)
    must_not: list[str] = field(default_factory=list)
    ui_mode: str = "text"
    practice_context: str | None = None
    user_response_to: str | None = None
    buttons: list[dict] | None = None
    timer_seconds: int | None = None


@dataclass
class EngineDecision:
    state: DialogueState
    action: str
    practice_id: str | None = None
    practice_step: int | None = None
    ui_mode: UIMode = UIMode.TEXT
    llm_contract: LLMContract | None = None
    reason_codes: list[str] = field(default_factory=list)
    confidence: float | None = None
    decision_source: Literal["model", "rules", "heuristic"] = "rules"


@dataclass
class ModuleError:
    module: str
    recoverable: bool
    error_code: str
    fallback_response: str | None = None


@dataclass
class SkippedState:
    state: DialogueState
    reason_code: str


@dataclass
class StateTransition:
    event_id: str
    transition_seq: int
    session_id: str
    from_state: DialogueState
    to_state: DialogueState
    trigger: str
    reason_codes: list[str] = field(default_factory=list)
    timestamp: datetime | None = None
    skipped: list[SkippedState] = field(default_factory=list)
