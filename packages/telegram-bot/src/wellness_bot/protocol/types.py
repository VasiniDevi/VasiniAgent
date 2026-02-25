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


# ---------------------------------------------------------------------------
# 2-level FSM enums (coaching pipeline)
# ---------------------------------------------------------------------------


class ConversationState(str, Enum):
    FREE_CHAT = "FREE_CHAT"
    EXPLORE = "EXPLORE"
    PRACTICE_OFFERED = "PRACTICE_OFFERED"
    PRACTICE_ACTIVE = "PRACTICE_ACTIVE"
    PRACTICE_PAUSED = "PRACTICE_PAUSED"
    FOLLOW_UP = "FOLLOW_UP"
    CRISIS = "CRISIS"


class PracticeState(str, Enum):
    CONSENT = "CONSENT"
    BASELINE = "BASELINE"
    STEP = "STEP"
    CHECKPOINT = "CHECKPOINT"
    ADAPT = "ADAPT"
    WRAP_UP = "WRAP_UP"
    FOLLOW_UP = "FOLLOW_UP"


class CoachingDecision(str, Enum):
    LISTEN = "LISTEN"
    EXPLORE = "EXPLORE"
    SUGGEST = "SUGGEST"
    GUIDE = "GUIDE"
    ANSWER = "ANSWER"


class ConsentStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


# ---------------------------------------------------------------------------
# Coaching pipeline dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EmotionalState:
    anxiety: float = 0.0
    rumination: float = 0.0
    avoidance: float = 0.0
    perfectionism: float = 0.0
    self_criticism: float = 0.0
    symptom_fixation: float = 0.0

    @property
    def dominant(self) -> str:
        fields = {
            "anxiety": self.anxiety,
            "rumination": self.rumination,
            "avoidance": self.avoidance,
            "perfectionism": self.perfectionism,
            "self_criticism": self.self_criticism,
            "symptom_fixation": self.symptom_fixation,
        }
        return max(fields, key=fields.get)  # type: ignore[arg-type]


@dataclass
class ContextState:
    risk_level: str
    emotional_state: EmotionalState
    readiness_for_practice: float
    coaching_hypotheses: list[str]
    confidence: float
    candidate_constraints: list[str]


@dataclass
class OpportunityResult:
    opportunity_score: float
    allow_proactive_suggest: bool
    reason_codes: list[str]
    cooldown_until: str | None = None


@dataclass
class PracticeCandidateRanked:
    practice_id: str
    final_score: float
    confidence: float
    reason_codes: list[str]
    blocked_by: list[str] | None = None
    alternative_ids: list[str] | None = None


@dataclass
class CoachDecision:
    decision: CoachingDecision
    selected_practice_id: str | None = None
    style: str = "warm_supportive"
    must_ask_consent: bool = False
