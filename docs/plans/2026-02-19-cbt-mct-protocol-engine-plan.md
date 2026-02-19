# CBT + MCT Protocol Engine — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add structured CBT+MCT protocol flows to @ONAHELPBOT — hybrid FSM, deterministic rule engine, 12-practice catalog, two-layer safety system, contract-bound LLM adapter.

**Architecture:** A+ approach — ProtocolEngine (code) + Practice content (YAML) + SQLite with repository abstraction. 7-module pipeline: Handler → SafetyClassifier → ProtocolEngine → RuleEngine → PracticeRunner → LLM Adapter → ProgressTracker.

**Tech Stack:** Python 3.12, aiogram 3, aiosqlite, pydantic 2, pyyaml, httpx, pytest + pytest-asyncio

**Design doc:** `docs/plans/2026-02-19-cbt-mct-protocol-engine-design.md`

---

## Phase 1: Foundation — Enums, Schema, Repository

### Task 1: Create protocol package with enums and types

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/__init__.py`
- Create: `packages/telegram-bot/src/wellness_bot/protocol/types.py`
- Test: `packages/telegram-bot/tests/test_protocol_types.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_protocol_types.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'wellness_bot.protocol'`

**Step 3: Write implementation**

```python
# src/wellness_bot/protocol/__init__.py
"""Protocol engine for structured CBT+MCT flows."""

# src/wellness_bot/protocol/types.py
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
```

**Step 4: Run test to verify it passes**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_protocol_types.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/ packages/telegram-bot/tests/test_protocol_types.py
git commit -m "feat(protocol): add enums and typed contracts for protocol engine"
```

---

### Task 2: Create database schema migration

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/schema.py`
- Test: `packages/telegram-bot/tests/test_protocol_schema.py`

**Step 1: Write the failing test**

```python
# tests/test_protocol_schema.py
"""Tests for protocol schema migration."""
import pytest
import aiosqlite

from wellness_bot.protocol.schema import apply_protocol_schema


@pytest.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = await aiosqlite.connect(db_path)
    yield conn
    await conn.close()


class TestProtocolSchema:
    async def test_creates_all_tables(self, db):
        await apply_protocol_schema(db)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        expected = {
            "dialogue_sessions",
            "state_transitions",
            "practice_sessions",
            "practice_checkpoints",
            "homework",
            "protocol_progress",
            "assessments",
            "safety_events",
            "processed_events",
            "technique_history",
            "validation_events",
        }
        assert expected.issubset(tables)

    async def test_idempotent(self, db):
        await apply_protocol_schema(db)
        await apply_protocol_schema(db)  # no error on second call

    async def test_one_active_session_constraint(self, db):
        await apply_protocol_schema(db)
        now = "2026-02-19T00:00:00Z"
        await db.execute(
            """INSERT INTO dialogue_sessions
               (id, user_id, session_type, current_state, started_at,
                last_user_activity_at, resumable, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            ("s1", 1, "new_user", "INTAKE", now, now, now, now),
        )
        await db.commit()
        with pytest.raises(Exception):  # UNIQUE constraint
            await db.execute(
                """INSERT INTO dialogue_sessions
                   (id, user_id, session_type, current_state, started_at,
                    last_user_activity_at, resumable, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                ("s2", 1, "returning", "INTAKE", now, now, now, now),
            )
            await db.commit()

    async def test_check_constraints(self, db):
        await apply_protocol_schema(db)
        now = "2026-02-19T00:00:00Z"
        with pytest.raises(Exception):  # invalid session_type
            await db.execute(
                """INSERT INTO dialogue_sessions
                   (id, user_id, session_type, current_state, started_at,
                    last_user_activity_at, resumable, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                ("s1", 1, "INVALID", "INTAKE", now, now, now, now),
            )
            await db.commit()

    async def test_rating_check_constraint(self, db):
        await apply_protocol_schema(db)
        now = "2026-02-19T00:00:00Z"
        # First create a valid session
        await db.execute(
            """INSERT INTO dialogue_sessions
               (id, user_id, session_type, current_state, started_at,
                last_user_activity_at, resumable, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            ("s1", 1, "new_user", "PRACTICE", now, now, now, now),
        )
        await db.commit()
        with pytest.raises(Exception):  # pre_rating out of range
            await db.execute(
                """INSERT INTO practice_sessions
                   (id, session_id, user_id, practice_id, practice_version,
                    step_schema_hash, priority_rank, current_step_index,
                    total_steps, status, pre_rating, started_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("p1", "s1", 1, "A2", "1.0", "hash", 15, 1, 4, "in_progress", 15, now, now, now),
            )
            await db.commit()
```

**Step 2: Run test to verify it fails**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_protocol_schema.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# src/wellness_bot/protocol/schema.py
"""Database schema for protocol engine tables."""
from __future__ import annotations

import aiosqlite

PROTOCOL_SCHEMA = """
CREATE TABLE IF NOT EXISTS dialogue_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_type TEXT NOT NULL CHECK(session_type IN
        ('new_user','returning','returning_long_gap','quick_checkin','crisis','resume')),
    current_state TEXT NOT NULL CHECK(current_state IN
        ('SAFETY_CHECK','ESCALATION','INTAKE','FORMULATION','GOAL_SETTING',
         'MODULE_SELECT','PRACTICE','REFLECTION','REFLECTION_LITE','HOMEWORK','SESSION_END')),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    end_reason TEXT CHECK(end_reason IN ('completed','user_stop','timeout','crisis_reentry') OR end_reason IS NULL),
    last_user_activity_at TEXT NOT NULL,
    resumable INTEGER NOT NULL DEFAULT 0 CHECK(resumable IN (0,1)),
    resume_practice_id TEXT,
    resume_step_index INTEGER,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_active
    ON dialogue_sessions(user_id, ended_at, last_user_activity_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_session
    ON dialogue_sessions(user_id) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS state_transitions (
    event_id TEXT PRIMARY KEY,
    transition_seq INTEGER NOT NULL,
    session_id TEXT NOT NULL REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT NOT NULL,
    reason_codes_json TEXT NOT NULL,
    skipped_json TEXT,
    timestamp_utc TEXT NOT NULL,
    UNIQUE(session_id, transition_seq)
);
CREATE INDEX IF NOT EXISTS idx_transitions_session
    ON state_transitions(session_id, transition_seq);

CREATE TABLE IF NOT EXISTS practice_sessions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL,
    practice_id TEXT NOT NULL,
    practice_version TEXT NOT NULL,
    step_schema_hash TEXT NOT NULL,
    priority_rank INTEGER NOT NULL,
    current_step_index INTEGER NOT NULL DEFAULT 1,
    total_steps INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK(status IN ('in_progress','completed','dropped','paused')),
    pre_rating INTEGER CHECK(pre_rating BETWEEN 0 AND 10),
    post_rating INTEGER CHECK(post_rating BETWEEN 0 AND 10),
    drop_reason TEXT CHECK(drop_reason IN ('timeout','user_stop','too_hard','crisis_reentry') OR drop_reason IS NULL),
    timer_state_json TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_practice_status
    ON practice_sessions(user_id, status, started_at);

CREATE TABLE IF NOT EXISTS practice_checkpoints (
    id TEXT PRIMARY KEY,
    practice_session_id TEXT NOT NULL REFERENCES practice_sessions(id) ON DELETE RESTRICT,
    step_index INTEGER NOT NULL,
    user_response TEXT,
    button_action TEXT CHECK(button_action IN
        ('next','fallback','branch_extended','branch_help','backup_practice','end') OR button_action IS NULL),
    fallback_used TEXT CHECK(fallback_used IN ('user_confused','cannot_now','too_hard') OR fallback_used IS NULL),
    timestamp_utc TEXT NOT NULL,
    UNIQUE(practice_session_id, step_index)
);

CREATE TABLE IF NOT EXISTS homework (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    practice_id TEXT NOT NULL,
    assignment_text TEXT NOT NULL,
    frequency TEXT CHECK(frequency IN ('daily','2x_day','weekly','once') OR frequency IS NULL),
    assigned_at TEXT NOT NULL,
    due_at TEXT,
    status TEXT NOT NULL DEFAULT 'assigned'
        CHECK(status IN ('assigned','completed','partial','skipped','expired')),
    completion_rating INTEGER CHECK(completion_rating BETWEEN 0 AND 10),
    completion_note TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_homework_pending ON homework(user_id, status, due_at);

CREATE TABLE IF NOT EXISTS protocol_progress (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    protocol_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('structured','organic')),
    current_session_number INTEGER NOT NULL DEFAULT 1,
    total_sessions INTEGER,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','completed','paused','abandoned')),
    maintaining_cycle TEXT,
    started_at TEXT NOT NULL,
    last_session_at TEXT,
    completed_at TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_protocol_user ON protocol_progress(user_id, status);

CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    instrument TEXT NOT NULL CHECK(instrument IN ('PHQ-2','GAD-2','custom_mood','custom_rumination')),
    score INTEGER NOT NULL,
    max_score INTEGER NOT NULL,
    responses_json TEXT NOT NULL,
    administered_at TEXT NOT NULL,
    session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_assessments_user ON assessments(user_id, instrument, administered_at);

CREATE TABLE IF NOT EXISTS safety_events (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    risk_level TEXT NOT NULL CHECK(risk_level IN ('SAFE','CAUTION_MILD','CAUTION_ELEVATED','CRISIS')),
    protocol_id TEXT CHECK(protocol_id IN ('S1','S2','S3','S4','S5','S6','S7') OR protocol_id IS NULL),
    immediacy TEXT CHECK(immediacy IN ('none','possible','imminent') OR immediacy IS NULL),
    signals_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('rules','model')),
    classifier_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    message_locale TEXT NOT NULL,
    resource_set_version TEXT NOT NULL,
    user_message_hash TEXT NOT NULL,
    user_message_raw TEXT,
    bot_response_text TEXT,
    handoff_status TEXT CHECK(handoff_status IN
        ('offered','accepted','connected','failed','timeout','declined') OR handoff_status IS NULL),
    resolution TEXT CHECK(resolution IN ('resolved','unresolved','no_response') OR resolution IS NULL),
    timestamp_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_safety_user ON safety_events(user_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_safety_crisis ON safety_events(risk_level) WHERE risk_level = 'CRISIS';

CREATE TABLE IF NOT EXISTS processed_events (
    idempotency_key TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_processed_ttl ON processed_events(processed_at);

CREATE TABLE IF NOT EXISTS technique_history (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    practice_id TEXT NOT NULL,
    times_used INTEGER NOT NULL DEFAULT 0,
    avg_effectiveness REAL,
    last_used_at TEXT,
    UNIQUE(user_id, practice_id)
);
CREATE INDEX IF NOT EXISTS idx_technique_user ON technique_history(user_id);

CREATE TABLE IF NOT EXISTS validation_events (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    validator_version TEXT NOT NULL,
    check_name TEXT NOT NULL,
    passed INTEGER NOT NULL CHECK(passed IN (0,1)),
    failure_reason TEXT,
    llm_response_hash TEXT,
    timestamp_utc TEXT NOT NULL
);
"""


async def apply_protocol_schema(db: aiosqlite.Connection) -> None:
    """Apply protocol engine schema. Idempotent (IF NOT EXISTS)."""
    await db.executescript(PROTOCOL_SCHEMA)
```

**Step 4: Run test**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_protocol_schema.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/schema.py packages/telegram-bot/tests/test_protocol_schema.py
git commit -m "feat(protocol): add database schema for protocol engine tables"
```

---

### Task 3: Create repository layer with UnitOfWork

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/repository.py`
- Test: `packages/telegram-bot/tests/test_protocol_repository.py`

**Step 1: Write the failing test**

```python
# tests/test_protocol_repository.py
"""Tests for protocol repository layer."""
import pytest
import aiosqlite
from datetime import datetime, timezone

from wellness_bot.protocol.schema import apply_protocol_schema
from wellness_bot.protocol.repository import SQLiteUnitOfWork
from wellness_bot.protocol.types import DialogueState, SessionType, RiskLevel


@pytest.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = await aiosqlite.connect(db_path)
    await apply_protocol_schema(conn)
    yield conn
    await conn.close()


class TestSQLiteUnitOfWork:
    async def test_session_create_and_get(self, db):
        now = datetime.now(timezone.utc).isoformat()
        async with SQLiteUnitOfWork(db) as uow:
            await uow.sessions.create(
                id="s1", user_id=1, session_type="new_user",
                current_state="INTAKE", started_at=now,
                last_user_activity_at=now, created_at=now, updated_at=now,
            )
        async with SQLiteUnitOfWork(db) as uow:
            session = await uow.sessions.get_active(user_id=1)
        assert session is not None
        assert session["id"] == "s1"
        assert session["current_state"] == "INTAKE"

    async def test_session_close(self, db):
        now = datetime.now(timezone.utc).isoformat()
        async with SQLiteUnitOfWork(db) as uow:
            await uow.sessions.create(
                id="s1", user_id=1, session_type="new_user",
                current_state="INTAKE", started_at=now,
                last_user_activity_at=now, created_at=now, updated_at=now,
            )
        async with SQLiteUnitOfWork(db) as uow:
            await uow.sessions.close(session_id="s1", end_reason="completed", ended_at=now)
        async with SQLiteUnitOfWork(db) as uow:
            session = await uow.sessions.get_active(user_id=1)
        assert session is None

    async def test_idempotency_check(self, db):
        async with SQLiteUnitOfWork(db) as uow:
            assert await uow.idempotency.is_processed("upd-123") is False
            await uow.idempotency.mark_processed("upd-123")
        async with SQLiteUnitOfWork(db) as uow:
            assert await uow.idempotency.is_processed("upd-123") is True

    async def test_safety_event_log(self, db):
        now = datetime.now(timezone.utc).isoformat()
        # Create session first
        async with SQLiteUnitOfWork(db) as uow:
            await uow.sessions.create(
                id="s1", user_id=1, session_type="new_user",
                current_state="SAFETY_CHECK", started_at=now,
                last_user_activity_at=now, created_at=now, updated_at=now,
            )
        async with SQLiteUnitOfWork(db) as uow:
            await uow.safety.log_event(
                id="se1", user_id=1, session_id="s1",
                risk_level="SAFE", signals_json="[]",
                confidence=0.95, source="rules",
                classifier_version="1.0", policy_version="1.0",
                message_locale="ru", resource_set_version="1.0",
                user_message_hash="abc123", timestamp_utc=now,
            )
        async with SQLiteUnitOfWork(db) as uow:
            events = await uow.safety.get_recent(user_id=1, window_minutes=60)
        assert len(events) == 1
        assert events[0]["risk_level"] == "SAFE"

    async def test_technique_history_upsert(self, db):
        async with SQLiteUnitOfWork(db) as uow:
            await uow.techniques.upsert_stats(
                id="th1", user_id=1, practice_id="A2", delta=3,
            )
        async with SQLiteUnitOfWork(db) as uow:
            await uow.techniques.upsert_stats(
                id="th2", user_id=1, practice_id="A2", delta=5,
            )
        async with SQLiteUnitOfWork(db) as uow:
            stats = await uow.techniques.get_stats(user_id=1)
        a2 = next(s for s in stats if s["practice_id"] == "A2")
        assert a2["times_used"] == 2
        assert a2["avg_effectiveness"] == 4.0  # (3+5)/2

    async def test_rollback_on_error(self, db):
        now = datetime.now(timezone.utc).isoformat()
        try:
            async with SQLiteUnitOfWork(db) as uow:
                await uow.sessions.create(
                    id="s1", user_id=1, session_type="new_user",
                    current_state="INTAKE", started_at=now,
                    last_user_activity_at=now, created_at=now, updated_at=now,
                )
                raise ValueError("simulated error")
        except ValueError:
            pass
        async with SQLiteUnitOfWork(db) as uow:
            session = await uow.sessions.get_active(user_id=1)
        assert session is None  # rolled back
```

**Step 2: Run test to verify it fails**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_protocol_repository.py -v
```
Expected: FAIL

**Step 3: Write implementation**

```python
# src/wellness_bot/protocol/repository.py
"""Repository layer with UnitOfWork for protocol engine."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Self

import aiosqlite


class SessionRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(self, **kwargs) -> None:
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        await self._db.execute(
            f"INSERT INTO dialogue_sessions ({cols}) VALUES ({placeholders})",
            tuple(kwargs.values()),
        )

    async def get_active(self, user_id: int) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM dialogue_sessions WHERE user_id = ? AND ended_at IS NULL",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))

    async def update_state(self, session_id: str, new_state: str, updated_at: str) -> None:
        await self._db.execute(
            "UPDATE dialogue_sessions SET current_state = ?, updated_at = ? WHERE id = ?",
            (new_state, updated_at, session_id),
        )

    async def close(self, session_id: str, end_reason: str, ended_at: str) -> None:
        await self._db.execute(
            "UPDATE dialogue_sessions SET ended_at = ?, end_reason = ?, "
            "current_state = 'SESSION_END', updated_at = ? WHERE id = ?",
            (ended_at, end_reason, ended_at, session_id),
        )

    async def touch_activity(self, session_id: str, timestamp: str) -> None:
        await self._db.execute(
            "UPDATE dialogue_sessions SET last_user_activity_at = ?, updated_at = ? WHERE id = ?",
            (timestamp, timestamp, session_id),
        )


class SafetyRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def log_event(self, **kwargs) -> None:
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        await self._db.execute(
            f"INSERT INTO safety_events ({cols}) VALUES ({placeholders})",
            tuple(kwargs.values()),
        )

    async def get_recent(self, user_id: int, window_minutes: int) -> list[dict]:
        since = datetime.now(timezone.utc)
        # Compute ISO cutoff
        from datetime import timedelta
        cutoff = (since - timedelta(minutes=window_minutes)).isoformat()
        cursor = await self._db.execute(
            "SELECT * FROM safety_events WHERE user_id = ? AND timestamp_utc >= ? ORDER BY timestamp_utc DESC",
            (user_id, cutoff),
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in await cursor.fetchall()]


class IdempotencyRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def is_processed(self, key: str) -> bool:
        cursor = await self._db.execute(
            "SELECT 1 FROM processed_events WHERE idempotency_key = ?", (key,)
        )
        return await cursor.fetchone() is not None

    async def mark_processed(self, key: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT OR IGNORE INTO processed_events (idempotency_key, processed_at) VALUES (?, ?)",
            (key, now),
        )


class TechniqueHistoryRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def upsert_stats(self, id: str, user_id: int, practice_id: str, delta: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """INSERT INTO technique_history (id, user_id, practice_id, times_used, avg_effectiveness, last_used_at)
               VALUES (?, ?, ?, 1, ?, ?)
               ON CONFLICT(user_id, practice_id) DO UPDATE SET
                   times_used = times_used + 1,
                   avg_effectiveness = (COALESCE(avg_effectiveness, 0) * times_used + ?) / (times_used + 1),
                   last_used_at = ?""",
            (id, user_id, practice_id, float(delta), now, float(delta), now),
        )

    async def get_stats(self, user_id: int) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM technique_history WHERE user_id = ?", (user_id,)
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in await cursor.fetchall()]


class SQLiteUnitOfWork:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db
        self.sessions = SessionRepository(db)
        self.safety = SafetyRepository(db)
        self.idempotency = IdempotencyRepository(db)
        self.techniques = TechniqueHistoryRepository(db)

    async def __aenter__(self) -> Self:
        await self._db.execute("BEGIN IMMEDIATE")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self._db.rollback()
        else:
            await self._db.commit()
```

**Step 4: Run test**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_protocol_repository.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/repository.py packages/telegram-bot/tests/test_protocol_repository.py
git commit -m "feat(protocol): add repository layer with UnitOfWork and SQLite implementation"
```

---

## Phase 2: Safety System

### Task 4: Create SafetyClassifier with hard rules

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/safety.py`
- Test: `packages/telegram-bot/tests/test_safety_classifier.py`

**Step 1: Write the failing test**

```python
# tests/test_safety_classifier.py
"""Tests for SafetyClassifier — hard rules layer."""
import pytest
from wellness_bot.protocol.safety import SafetyClassifier, SafetyResult
from wellness_bot.protocol.types import RiskLevel


@pytest.fixture
def classifier():
    return SafetyClassifier(classifier_version="1.0", policy_version="1.0")


class TestHardRules:
    def test_suicide_explicit_ru(self, classifier):
        result = classifier.check_hard_rules("хочу умереть")
        assert result is not None
        assert result.risk_level == RiskLevel.CRISIS
        assert result.protocol_id == "S1"

    def test_suicide_explicit_en(self, classifier):
        result = classifier.check_hard_rules("I want to kill myself")
        assert result is not None
        assert result.risk_level == RiskLevel.CRISIS
        assert result.protocol_id == "S1"

    def test_self_harm(self, classifier):
        result = classifier.check_hard_rules("я режу себя каждый вечер")
        assert result is not None
        assert result.protocol_id == "S1"

    def test_violence(self, classifier):
        result = classifier.check_hard_rules("я убью его")
        assert result is not None
        assert result.protocol_id == "S2"

    def test_psychosis(self, classifier):
        result = classifier.check_hard_rules("голоса говорят мне что делать")
        assert result is not None
        assert result.protocol_id == "S3"

    def test_domestic_violence(self, classifier):
        result = classifier.check_hard_rules("муж бьёт меня")
        assert result is not None
        assert result.protocol_id == "S6"

    def test_safe_message(self, classifier):
        result = classifier.check_hard_rules("Сегодня хороший день, настроение 7")
        assert result is None

    def test_safe_with_partial_keyword(self, classifier):
        """'умереть' in context of discussing death abstractly should still trigger."""
        result = classifier.check_hard_rules("Иногда хочу умереть")
        assert result is not None
        assert result.risk_level == RiskLevel.CRISIS

    def test_case_insensitive(self, classifier):
        result = classifier.check_hard_rules("ХОЧУ УМЕРЕТЬ")
        assert result is not None


class TestClassify:
    async def test_hard_rules_bypass_llm(self, classifier):
        """Hard rules should return immediately without calling LLM."""
        result = await classifier.classify("хочу покончить с собой", context=[])
        assert result.risk_level == RiskLevel.CRISIS
        assert result.source == "rules"

    async def test_safe_message_without_llm(self, classifier):
        """Without LLM provider, safe messages should return CAUTION_MILD (uncertain)."""
        result = await classifier.classify("привет, как дела", context=[])
        # Without LLM, we can't be certain → CAUTION_MILD
        assert result.risk_level == RiskLevel.CAUTION_MILD
        assert result.source == "heuristic"
```

**Step 2: Run test to verify it fails**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_safety_classifier.py -v
```

**Step 3: Write implementation**

```python
# src/wellness_bot/protocol/safety.py
"""Two-layer safety classifier: hard rules + LLM."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from wellness_bot.protocol.types import RiskLevel


@dataclass
class SafetyResult:
    risk_level: RiskLevel
    protocol_id: str | None = None
    immediacy: str = "none"  # none | possible | imminent
    signals: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = "rules"  # rules | model | heuristic
    classifier_version: str = "1.0"
    policy_version: str = "1.0"

    def message_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()


# Hard-coded crisis patterns — Layer 1
_CRISIS_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, protocol_id, signal_name)
    # S1: Suicide / Self-harm
    (r"хочу\s+умереть", "S1", "suicide_explicit_ru"),
    (r"покончить\s+с\s+собой", "S1", "suicide_explicit_ru"),
    (r"суицид", "S1", "suicide_keyword_ru"),
    (r"убить\s+себя", "S1", "suicide_explicit_ru"),
    (r"не\s+хочу\s+жить", "S1", "suicide_wish_ru"),
    (r"лучше\s+бы\s+меня\s+не\s+было", "S1", "suicide_wish_ru"),
    (r"kill\s+my\s*self", "S1", "suicide_explicit_en"),
    (r"want\s+to\s+die", "S1", "suicide_explicit_en"),
    (r"end\s+my\s+life", "S1", "suicide_explicit_en"),
    (r"реж[уе]\s+себ[яе]", "S1", "self_harm_ru"),
    (r"причин(ить|яю)\s+себе\s+(боль|вред)", "S1", "self_harm_ru"),
    (r"hurt\s+my\s*self", "S1", "self_harm_en"),
    # S2: Violence to others
    (r"убь[юёе]\s+(его|её|их|тебя)", "S2", "violence_threat_ru"),
    (r"хочу\s+навредить", "S2", "violence_intent_ru"),
    (r"kill\s+(him|her|them)", "S2", "violence_threat_en"),
    # S3: Psychosis
    (r"голоса\s+говорят", "S3", "psychosis_hallucination_ru"),
    (r"за\s+мной\s+следят", "S3", "psychosis_paranoia_ru"),
    (r"я\s+избранн", "S3", "psychosis_grandiosity_ru"),
    # S6: Domestic violence
    (r"(муж|парень|партн[её]р)\s+(бь[её]т|удари)", "S6", "dv_physical_ru"),
    (r"бь[её]т\s+меня", "S6", "dv_physical_ru"),
    (r"боюсь\s+партн[её]р", "S6", "dv_fear_ru"),
]

_COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), proto, sig) for p, proto, sig in _CRISIS_PATTERNS]


class SafetyClassifier:
    def __init__(
        self,
        classifier_version: str = "1.0",
        policy_version: str = "1.0",
        llm_provider=None,
    ) -> None:
        self.classifier_version = classifier_version
        self.policy_version = policy_version
        self._llm = llm_provider

    def check_hard_rules(self, text: str) -> SafetyResult | None:
        """Layer 1: instant pattern matching. Returns None if no match."""
        for pattern, protocol_id, signal_name in _COMPILED_PATTERNS:
            if pattern.search(text):
                return SafetyResult(
                    risk_level=RiskLevel.CRISIS,
                    protocol_id=protocol_id,
                    immediacy="possible",
                    signals=[signal_name],
                    confidence=1.0,
                    source="rules",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )
        return None

    async def classify(self, text: str, context: list[dict]) -> SafetyResult:
        """Full two-layer classification: hard rules first, then LLM."""
        # Layer 1: hard rules
        hard_result = self.check_hard_rules(text)
        if hard_result is not None:
            return hard_result

        # Layer 2: LLM classifier (if available)
        if self._llm is not None:
            return await self._classify_with_llm(text, context)

        # No LLM available: uncertain → CAUTION_MILD (never SAFE when uncertain)
        return SafetyResult(
            risk_level=RiskLevel.CAUTION_MILD,
            signals=["no_llm_classifier"],
            confidence=0.0,
            source="heuristic",
            classifier_version=self.classifier_version,
            policy_version=self.policy_version,
        )

    async def _classify_with_llm(self, text: str, context: list[dict]) -> SafetyResult:
        """Layer 2: LLM-based classification using haiku."""
        # TODO: implement in Task 5 (LLM integration)
        raise NotImplementedError
```

**Step 4: Run test**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_safety_classifier.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/safety.py packages/telegram-bot/tests/test_safety_classifier.py
git commit -m "feat(protocol): add SafetyClassifier with hard rules layer"
```

---

### Task 5: Add LLM layer to SafetyClassifier

**Files:**
- Modify: `packages/telegram-bot/src/wellness_bot/protocol/safety.py`
- Test: `packages/telegram-bot/tests/test_safety_classifier.py` (extend)

**Step 1: Write the failing test**

Add to `tests/test_safety_classifier.py`:

```python
from unittest.mock import AsyncMock, MagicMock


class TestLLMClassifier:
    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.chat = AsyncMock()
        return llm

    @pytest.fixture
    def classifier_with_llm(self, mock_llm):
        return SafetyClassifier(llm_provider=mock_llm)

    async def test_llm_crisis_high_confidence(self, classifier_with_llm, mock_llm):
        from vasini.llm.types import LLMResponse
        mock_llm.chat.return_value = LLMResponse(
            content='{"risk_level":"CRISIS","protocol":"S1","immediacy":"imminent","signals":["suicidal_ideation"],"confidence":0.9}',
            model="claude-haiku",
            usage={"input_tokens": 50, "output_tokens": 30},
        )
        result = await classifier_with_llm.classify("Я больше не могу так жить", context=[])
        assert result.risk_level == RiskLevel.CRISIS
        assert result.source == "model"

    async def test_llm_safe_high_confidence(self, classifier_with_llm, mock_llm):
        from vasini.llm.types import LLMResponse
        mock_llm.chat.return_value = LLMResponse(
            content='{"risk_level":"SAFE","protocol":null,"immediacy":"none","signals":[],"confidence":0.95}',
            model="claude-haiku",
            usage={"input_tokens": 50, "output_tokens": 30},
        )
        result = await classifier_with_llm.classify("Сегодня хорошо поспал", context=[])
        assert result.risk_level == RiskLevel.SAFE

    async def test_llm_low_confidence_defaults_to_caution(self, classifier_with_llm, mock_llm):
        from vasini.llm.types import LLMResponse
        mock_llm.chat.return_value = LLMResponse(
            content='{"risk_level":"SAFE","protocol":null,"immediacy":"none","signals":[],"confidence":0.4}',
            model="claude-haiku",
            usage={"input_tokens": 50, "output_tokens": 30},
        )
        result = await classifier_with_llm.classify("мне всё равно", context=[])
        assert result.risk_level == RiskLevel.CAUTION_MILD  # never SAFE when uncertain

    async def test_llm_crisis_low_confidence_still_escalates(self, classifier_with_llm, mock_llm):
        from vasini.llm.types import LLMResponse
        mock_llm.chat.return_value = LLMResponse(
            content='{"risk_level":"CRISIS","protocol":"S1","immediacy":"possible","signals":["ambiguous"],"confidence":0.3}',
            model="claude-haiku",
            usage={"input_tokens": 50, "output_tokens": 30},
        )
        result = await classifier_with_llm.classify("не вижу смысла", context=[])
        assert result.risk_level == RiskLevel.CRISIS  # safety > precision

    async def test_llm_timeout_fallback(self, classifier_with_llm, mock_llm):
        mock_llm.chat.side_effect = TimeoutError("LLM timeout")
        result = await classifier_with_llm.classify("что-то случилось", context=[])
        assert result.risk_level == RiskLevel.CAUTION_MILD
        assert result.source == "heuristic"
```

**Step 2: Run test to verify it fails**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_safety_classifier.py::TestLLMClassifier -v
```

**Step 3: Implement `_classify_with_llm`**

Replace the `_classify_with_llm` method in `safety.py`:

```python
    async def _classify_with_llm(self, text: str, context: list[dict]) -> SafetyResult:
        """Layer 2: LLM-based classification using haiku."""
        import json
        from vasini.llm.types import Message

        context_str = " | ".join(
            f"{m.get('role', '?')}: {m.get('content', '')[:100]}"
            for m in context[-3:]
        )

        system = (
            "You are a safety classifier for a wellness bot. "
            "Classify this message for risk level. "
            'Respond ONLY with JSON: {"risk_level":"SAFE|CAUTION_MILD|CAUTION_ELEVATED|CRISIS",'
            '"protocol":null or "S1"|"S2"|"S3"|"S4"|"S5"|"S6"|"S7",'
            '"immediacy":"none|possible|imminent",'
            '"signals":["list"],"confidence":0.0-1.0}'
        )

        prompt = f"User message: \"{text}\"\nRecent context: \"{context_str}\""

        try:
            response = await self._llm.chat(
                messages=[Message(role="user", content=prompt)],
                system=system,
                model="claude-haiku-4-5-20251001",
            )
            data = json.loads(response.content)

            risk = RiskLevel(data["risk_level"])
            confidence = float(data.get("confidence", 0.5))

            # Classification logic per design:
            if confidence >= 0.7:
                return SafetyResult(
                    risk_level=risk,
                    protocol_id=data.get("protocol"),
                    immediacy=data.get("immediacy", "none"),
                    signals=data.get("signals", []),
                    confidence=confidence,
                    source="model",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )
            elif risk == RiskLevel.CRISIS:
                # Safety > precision: escalate even at low confidence
                return SafetyResult(
                    risk_level=RiskLevel.CRISIS,
                    protocol_id=data.get("protocol"),
                    immediacy=data.get("immediacy", "possible"),
                    signals=data.get("signals", []) + ["low_confidence_crisis"],
                    confidence=confidence,
                    source="model",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )
            else:
                # Low confidence, not crisis → CAUTION_MILD (never SAFE when uncertain)
                return SafetyResult(
                    risk_level=RiskLevel.CAUTION_MILD,
                    signals=data.get("signals", []) + ["low_confidence"],
                    confidence=confidence,
                    source="model",
                    classifier_version=self.classifier_version,
                    policy_version=self.policy_version,
                )

        except Exception:
            # LLM failed → uncertain → CAUTION_MILD
            return SafetyResult(
                risk_level=RiskLevel.CAUTION_MILD,
                signals=["llm_error"],
                confidence=0.0,
                source="heuristic",
                classifier_version=self.classifier_version,
                policy_version=self.policy_version,
            )
```

**Step 4: Run test**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_safety_classifier.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/safety.py packages/telegram-bot/tests/test_safety_classifier.py
git commit -m "feat(protocol): add LLM layer to SafetyClassifier with confidence logic"
```

---

## Phase 3: Protocol Engine (FSM)

### Task 6: Create ProtocolEngine with state transitions

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/engine.py`
- Test: `packages/telegram-bot/tests/test_protocol_engine.py`

**Step 1: Write the failing test**

```python
# tests/test_protocol_engine.py
"""Tests for ProtocolEngine FSM."""
import pytest
from wellness_bot.protocol.engine import ProtocolEngine
from wellness_bot.protocol.types import DialogueState, SessionType, RiskLevel, CautionLevel


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
```

**Step 2: Run test to verify it fails**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_protocol_engine.py -v
```

**Step 3: Write implementation**

```python
# src/wellness_bot/protocol/engine.py
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
```

**Step 4: Run test**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_protocol_engine.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/engine.py packages/telegram-bot/tests/test_protocol_engine.py
git commit -m "feat(protocol): add ProtocolEngine with FSM transitions and session classifier"
```

---

## Phase 4: Rule Engine

### Task 7: Create RuleEngine with decision logic

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/rules.py`
- Test: `packages/telegram-bot/tests/test_rule_engine.py`

**Step 1: Write the failing test**

```python
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
        ids = {c.practice_id for c in candidates}
        assert "C1" not in ids  # Socratic blocked at 8+
        assert "C3" not in ids  # experiment blocked
        assert "A3" in ids or "A2" in ids  # stabilization allowed

    def test_low_distress_allows_all(self, engine):
        candidates = engine.get_eligible(
            distress=2, cycle=MaintainingCycle.AVOIDANCE,
            time_budget=20, readiness=Readiness.ACTION,
            caution=CautionLevel.NONE,
        )
        ids = {c.practice_id for c in candidates}
        assert "C3" in ids  # experiment allowed
        assert "C1" in ids  # Socratic allowed

    def test_2min_budget_limited(self, engine):
        candidates = engine.get_eligible(
            distress=5, cycle=MaintainingCycle.RUMINATION,
            time_budget=2, readiness=Readiness.ACTION,
            caution=CautionLevel.NONE,
        )
        ids = {c.practice_id for c in candidates}
        assert ids.issubset({"U2", "M3", "A2"})

    def test_caution_elevated_blocks_exposure(self, engine):
        candidates = engine.get_eligible(
            distress=5, cycle=MaintainingCycle.AVOIDANCE,
            time_budget=20, readiness=Readiness.ACTION,
            caution=CautionLevel.ELEVATED,
        )
        ids = {c.practice_id for c in candidates}
        assert "C3" not in ids  # experiment blocked at elevated
        assert "C1" not in ids  # Socratic (confrontational) blocked

    def test_precontemplation_only_basics(self, engine):
        candidates = engine.get_eligible(
            distress=3, cycle=MaintainingCycle.RUMINATION,
            time_budget=10, readiness=Readiness.PRECONTEMPLATION,
            caution=CautionLevel.NONE,
        )
        ids = {c.practice_id for c in candidates}
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
        # U2 has priority_rank=1 (lowest), but may not match cycle
        # A2 has priority_rank=15, A3 has 16
        # Primary should be A2 (lower rank among first-line matches)
        assert result.primary.practice_id == "A2"
```

**Step 2: Run test**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_rule_engine.py -v
```

**Step 3: Write implementation**

```python
# src/wellness_bot/protocol/rules.py
"""Deterministic rule engine for practice selection."""
from __future__ import annotations

from dataclasses import dataclass
from wellness_bot.protocol.types import (
    MaintainingCycle, Readiness, CautionLevel,
)

# Practice catalog v1 — defined in code, mirrors YAML
_CATALOG: list[dict] = [
    {"id": "M2", "cat": "monitoring", "dur_min": 2, "dur_max": 5, "rank": 10, "cycles": ["rumination", "worry"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "contemplation"},
    {"id": "M3", "cat": "monitoring", "dur_min": 1, "dur_max": 1, "rank": 5, "cycles": [],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "precontemplation"},
    {"id": "A1", "cat": "attention", "dur_min": 10, "dur_max": 12, "rank": 20, "cycles": ["rumination", "worry", "symptom_fixation"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "action"},
    {"id": "A2", "cat": "attention", "dur_min": 2, "dur_max": 5, "rank": 15, "cycles": ["rumination", "worry"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "contemplation"},
    {"id": "A3", "cat": "attention", "dur_min": 2, "dur_max": 5, "rank": 16, "cycles": ["rumination", "worry", "self_criticism"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "contemplation"},
    {"id": "A6", "cat": "attention", "dur_min": 2, "dur_max": 3, "rank": 25, "cycles": ["symptom_fixation", "avoidance"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "action"},
    {"id": "C1", "cat": "cognitive", "dur_min": 5, "dur_max": 10, "rank": 30, "cycles": ["avoidance", "perfectionism"],
     "blocked_distress": 8, "blocked_caution_elevated": True, "min_readiness": "action"},
    {"id": "C2", "cat": "cognitive", "dur_min": 5, "dur_max": 7, "rank": 31, "cycles": ["worry"],
     "blocked_distress": 8, "blocked_caution_elevated": False, "min_readiness": "action"},
    {"id": "C3", "cat": "cognitive", "dur_min": 10, "dur_max": 20, "rank": 35, "cycles": ["avoidance", "worry", "perfectionism"],
     "blocked_distress": 8, "blocked_caution_elevated": True, "min_readiness": "action"},
    {"id": "C5", "cat": "cognitive", "dur_min": 3, "dur_max": 5, "rank": 28, "cycles": ["self_criticism", "perfectionism"],
     "blocked_distress": 8, "blocked_caution_elevated": False, "min_readiness": "contemplation"},
    {"id": "B1", "cat": "behavioral", "dur_min": 5, "dur_max": 10, "rank": 22, "cycles": ["avoidance", "rumination"],
     "blocked_distress": 8, "blocked_caution_elevated": False, "min_readiness": "action"},
    {"id": "U2", "cat": "micro", "dur_min": 1, "dur_max": 1, "rank": 1, "cycles": [],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "precontemplation"},
]

# First-line mappings
_FIRST_LINE: dict[str, list[str]] = {
    "rumination": ["A2", "A3", "M2"],
    "worry": ["A2", "A3", "C2"],
    "avoidance": ["C3", "B1"],
    "perfectionism": ["C5", "C3"],
    "self_criticism": ["C5", "A3"],
    "symptom_fixation": ["A6", "A1", "A3"],
}

_SECOND_LINE: dict[str, list[str]] = {
    "rumination": ["A1", "B1"],
    "worry": ["A1", "C3"],
    "avoidance": ["C1"],
    "perfectionism": ["M2"],
    "self_criticism": ["C1"],
    "symptom_fixation": ["C2"],
}

_READINESS_ORDER = ["precontemplation", "contemplation", "action", "maintenance"]


@dataclass
class PracticeCandidate:
    practice_id: str
    score: float
    priority_rank: int


@dataclass
class SelectionResult:
    primary: PracticeCandidate
    backup: PracticeCandidate | None


class RuleEngine:
    def get_eligible(
        self,
        distress: int,
        cycle: MaintainingCycle,
        time_budget: int,
        readiness: Readiness,
        caution: CautionLevel,
    ) -> list[dict]:
        """Step 2: Hard filter — return eligible practices."""
        readiness_idx = _READINESS_ORDER.index(readiness.value)
        eligible = []
        for p in _CATALOG:
            # Distress gate
            if p["blocked_distress"] is not None and distress >= p["blocked_distress"]:
                continue
            # Caution gate
            if caution == CautionLevel.ELEVATED and p["blocked_caution_elevated"]:
                continue
            # Time gate
            if p["dur_min"] > time_budget:
                continue
            # Readiness gate
            p_readiness_idx = _READINESS_ORDER.index(p["min_readiness"])
            if readiness_idx < p_readiness_idx:
                continue
            # Precontemplation: only M3 and U2
            if readiness == Readiness.PRECONTEMPLATION and p["id"] not in ("M3", "U2"):
                continue
            eligible.append(p)
        return eligible

    def select(
        self,
        distress: int,
        cycle: MaintainingCycle,
        time_budget: int,
        readiness: Readiness,
        caution: CautionLevel,
        technique_history: dict,
    ) -> SelectionResult:
        """Full 7-step selection pipeline."""
        # Step 2: hard filter
        eligible = self.get_eligible(distress, cycle, time_budget, readiness, caution)

        first_line = _FIRST_LINE.get(cycle.value, [])
        second_line = _SECOND_LINE.get(cycle.value, [])

        scored: list[PracticeCandidate] = []
        for p in eligible:
            pid = p["id"]
            # Step 3: cycle match
            if pid in first_line:
                cycle_match = 1.0
            elif pid in second_line:
                cycle_match = 0.5
            elif not p["cycles"]:  # universal (M3, U2)
                cycle_match = 0.3
            else:
                cycle_match = 0.0

            # Step 4: score
            history = technique_history.get(pid, {})
            times_used = history.get("times_used", 0)
            avg_eff = history.get("avg_effectiveness", 5.0)

            effectiveness = avg_eff / 10.0
            repetition = 1.0 if times_used >= 3 else (0.5 if times_used >= 1 else 0.0)
            novelty = 1.0 if times_used == 0 else (0.5 if times_used < 3 else 0.0)

            raw = (
                cycle_match * 0.4
                + effectiveness * 0.3
                - repetition * 0.2
                + novelty * 0.1
            )
            score = max(0.0, min(1.0, raw))

            scored.append(PracticeCandidate(
                practice_id=pid,
                score=score,
                priority_rank=p["rank"],
            ))

        # Step 5: sort by score desc, then priority_rank asc (tiebreaker)
        scored.sort(key=lambda c: (-c.score, c.priority_rank))

        if not scored:
            # Fallback: U2 is always safe
            return SelectionResult(
                primary=PracticeCandidate("U2", 0.1, 1),
                backup=None,
            )

        primary = scored[0]
        backup = scored[1] if len(scored) > 1 else None

        return SelectionResult(primary=primary, backup=backup)
```

**Step 4: Run test**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_rule_engine.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/rules.py packages/telegram-bot/tests/test_rule_engine.py
git commit -m "feat(protocol): add RuleEngine with deterministic practice selection"
```

---

## Phase 5: Practice Runner

### Task 8: Create YAML practice loader with validation

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/practice_loader.py`
- Create: `packs/wellness-cbt/practices/U2-grounding.yaml`
- Create: `packs/wellness-cbt/practices/A2-postponement.yaml`
- Test: `packages/telegram-bot/tests/test_practice_loader.py`

**Step 1: Write the failing test**

```python
# tests/test_practice_loader.py
"""Tests for YAML practice loader with validation."""
import pytest
from pathlib import Path
from wellness_bot.protocol.practice_loader import PracticeLoader, Practice, PracticeValidationError


@pytest.fixture
def loader(tmp_path):
    return PracticeLoader(practices_dir=tmp_path)


@pytest.fixture
def valid_yaml(tmp_path):
    content = """
id: U2
version: "1.0"
step_schema_hash: "sha256:test"
name_ru: "3-3-3 заземление"
name_en: "3-3-3 Grounding"
category: micro
goal: "Прервать руминацию через сенсорный якорь"
duration_min: 1
duration_max: 1
priority_rank: 1

prerequisites:
  needs_formulation: false
  min_time_budget: 1
  min_readiness: precontemplation

safety_overrides:
  blocked_in_caution_elevated: false
  blocked_if_distress_gte: null

maintaining_cycles: []

steps:
  - index: 1
    instruction_ru: "Назовите 3 вещи, которые видите."
    ui_mode: text
    checkpoint: false
    fallback:
      user_confused: "Просто посмотрите вокруг и назовите 3 предмета."
      cannot_now: "Ничего, попробуем позже."
      too_hard: "Начните с одной вещи."
  - index: 2
    instruction_ru: "Назовите 3 звука."
    ui_mode: text
    checkpoint: false
    fallback:
      user_confused: "Прислушайтесь. Какие звуки слышите?"
      cannot_now: "Хорошо, пропустим."
      too_hard: "Назовите хотя бы один звук."
  - index: 3
    instruction_ru: "Назовите 3 ощущения в теле."
    ui_mode: buttons
    buttons:
      - label: "Готово"
        action: next
    checkpoint: true
    fallback:
      user_confused: "Что чувствуете? Тепло, холод, давление?"
      cannot_now: "Не страшно. Главное — вы попробовали."
      too_hard: "Просто отметьте одно ощущение."

outcome:
  pre_rating: {type: rating, label: "Тревога", scale: "0-10"}
  post_rating: {type: rating, label: "Тревога", scale: "0-10"}
  completed: true
  drop_reason: null
  tracking: null

resume_compatibility:
  practice_id: U2
  version: "1.0"
  step_schema_hash: "sha256:test"
"""
    (tmp_path / "U2-grounding.yaml").write_text(content)
    return tmp_path


class TestPracticeLoader:
    def test_load_valid_practice(self, valid_yaml):
        loader = PracticeLoader(practices_dir=valid_yaml)
        practices = loader.load_all()
        assert "U2" in practices
        p = practices["U2"]
        assert p.name_ru == "3-3-3 заземление"
        assert len(p.steps) == 3

    def test_step_index_continuity(self, valid_yaml):
        loader = PracticeLoader(practices_dir=valid_yaml)
        practices = loader.load_all()
        p = practices["U2"]
        indices = [s.index for s in p.steps]
        assert indices == [1, 2, 3]

    def test_all_fallback_keys_present(self, valid_yaml):
        loader = PracticeLoader(practices_dir=valid_yaml)
        practices = loader.load_all()
        for step in practices["U2"].steps:
            assert "user_confused" in step.fallback
            assert "cannot_now" in step.fallback
            assert "too_hard" in step.fallback

    def test_button_action_enum_validated(self, valid_yaml):
        loader = PracticeLoader(practices_dir=valid_yaml)
        practices = loader.load_all()
        step3 = practices["U2"].steps[2]
        assert step3.buttons[0]["action"] == "next"

    def test_missing_fallback_key_fails(self, tmp_path):
        bad = """
id: BAD
version: "1.0"
step_schema_hash: "sha256:bad"
name_ru: "Bad"
name_en: "Bad"
category: micro
goal: "test"
duration_min: 1
duration_max: 1
priority_rank: 99
prerequisites: {needs_formulation: false, min_time_budget: 1, min_readiness: precontemplation}
safety_overrides: {blocked_in_caution_elevated: false, blocked_if_distress_gte: null}
maintaining_cycles: []
steps:
  - index: 1
    instruction_ru: "Test"
    ui_mode: text
    checkpoint: false
    fallback:
      user_confused: "ok"
outcome: {pre_rating: null, post_rating: null, completed: true, drop_reason: null, tracking: null}
resume_compatibility: {practice_id: BAD, version: "1.0", step_schema_hash: "sha256:bad"}
"""
        (tmp_path / "BAD-test.yaml").write_text(bad)
        loader = PracticeLoader(practices_dir=tmp_path)
        with pytest.raises(PracticeValidationError, match="fallback"):
            loader.load_all()

    def test_step_index_gap_fails(self, tmp_path):
        bad = """
id: GAP
version: "1.0"
step_schema_hash: "sha256:gap"
name_ru: "Gap"
name_en: "Gap"
category: micro
goal: "test"
duration_min: 1
duration_max: 1
priority_rank: 99
prerequisites: {needs_formulation: false, min_time_budget: 1, min_readiness: precontemplation}
safety_overrides: {blocked_in_caution_elevated: false, blocked_if_distress_gte: null}
maintaining_cycles: []
steps:
  - index: 1
    instruction_ru: "Step 1"
    ui_mode: text
    checkpoint: false
    fallback: {user_confused: "a", cannot_now: "b", too_hard: "c"}
  - index: 3
    instruction_ru: "Step 3 (gap!)"
    ui_mode: text
    checkpoint: false
    fallback: {user_confused: "a", cannot_now: "b", too_hard: "c"}
outcome: {pre_rating: null, post_rating: null, completed: true, drop_reason: null, tracking: null}
resume_compatibility: {practice_id: GAP, version: "1.0", step_schema_hash: "sha256:gap"}
"""
        (tmp_path / "GAP-test.yaml").write_text(bad)
        loader = PracticeLoader(practices_dir=tmp_path)
        with pytest.raises(PracticeValidationError, match="continuity"):
            loader.load_all()
```

**Step 2: Run test**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_practice_loader.py -v
```

**Step 3: Write implementation**

```python
# src/wellness_bot/protocol/practice_loader.py
"""YAML practice loader with fail-fast validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


_VALID_CATEGORIES = {"monitoring", "attention", "cognitive", "behavioral", "micro"}
_VALID_UI_MODES = {"text", "buttons", "timer", "text_input"}
_VALID_BUTTON_ACTIONS = {"next", "fallback", "branch_extended", "branch_help", "backup_practice", "end"}
_REQUIRED_FALLBACK_KEYS = {"user_confused", "cannot_now", "too_hard"}


class PracticeValidationError(Exception):
    pass


@dataclass
class PracticeStep:
    index: int
    instruction_ru: str
    ui_mode: str
    checkpoint: bool
    fallback: dict[str, str]
    buttons: list[dict] | None = None


@dataclass
class Practice:
    id: str
    version: str
    step_schema_hash: str
    name_ru: str
    name_en: str
    category: str
    goal: str
    duration_min: int
    duration_max: int
    priority_rank: int
    prerequisites: dict
    safety_overrides: dict
    maintaining_cycles: list[str]
    steps: list[PracticeStep]
    outcome: dict
    resume_compatibility: dict


class PracticeLoader:
    def __init__(self, practices_dir: Path | str) -> None:
        self._dir = Path(practices_dir)

    def load_all(self) -> dict[str, Practice]:
        practices: dict[str, Practice] = {}
        for path in sorted(self._dir.glob("*.yaml")):
            practice = self._load_one(path)
            practices[practice.id] = practice
        return practices

    def _load_one(self, path: Path) -> Practice:
        with open(path) as f:
            data = yaml.safe_load(f)

        pid = data["id"]

        # Validate category
        if data.get("category") not in _VALID_CATEGORIES:
            raise PracticeValidationError(f"{pid}: invalid category '{data.get('category')}'")

        # Validate and build steps
        steps = []
        raw_steps = data.get("steps", [])
        expected_index = 1
        for s in raw_steps:
            idx = s["index"]
            if idx != expected_index:
                raise PracticeValidationError(
                    f"{pid}: step index continuity broken — expected {expected_index}, got {idx}"
                )
            expected_index += 1

            # Validate ui_mode
            if s.get("ui_mode") not in _VALID_UI_MODES:
                raise PracticeValidationError(f"{pid} step {idx}: invalid ui_mode '{s.get('ui_mode')}'")

            # Validate fallback keys
            fallback = s.get("fallback", {})
            missing = _REQUIRED_FALLBACK_KEYS - set(fallback.keys())
            if missing:
                raise PracticeValidationError(
                    f"{pid} step {idx}: missing fallback keys: {missing}"
                )

            # Validate button actions
            buttons = s.get("buttons")
            if buttons:
                for btn in buttons:
                    if btn.get("action") not in _VALID_BUTTON_ACTIONS:
                        raise PracticeValidationError(
                            f"{pid} step {idx}: invalid button action '{btn.get('action')}'"
                        )

            steps.append(PracticeStep(
                index=idx,
                instruction_ru=s["instruction_ru"],
                ui_mode=s["ui_mode"],
                checkpoint=s.get("checkpoint", False),
                fallback=fallback,
                buttons=buttons,
            ))

        return Practice(
            id=pid,
            version=data["version"],
            step_schema_hash=data.get("step_schema_hash", ""),
            name_ru=data["name_ru"],
            name_en=data.get("name_en", ""),
            category=data["category"],
            goal=data["goal"],
            duration_min=data["duration_min"],
            duration_max=data["duration_max"],
            priority_rank=data["priority_rank"],
            prerequisites=data.get("prerequisites", {}),
            safety_overrides=data.get("safety_overrides", {}),
            maintaining_cycles=data.get("maintaining_cycles", []),
            steps=steps,
            outcome=data.get("outcome", {}),
            resume_compatibility=data.get("resume_compatibility", {}),
        )
```

**Step 4: Run test**

```bash
cd packages/telegram-bot && python3 -m pytest tests/test_practice_loader.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/practice_loader.py packages/telegram-bot/tests/test_practice_loader.py
git commit -m "feat(protocol): add YAML practice loader with fail-fast validation"
```

---

### Task 9: Create practice YAML files for v1 catalog (12 practices)

**Files:**
- Create: `packs/wellness-cbt/practices/M2-rumination-monitoring.yaml`
- Create: `packs/wellness-cbt/practices/M3-mood-checkin.yaml`
- Create: `packs/wellness-cbt/practices/A1-att.yaml`
- Create: `packs/wellness-cbt/practices/A2-postponement.yaml`
- Create: `packs/wellness-cbt/practices/A3-detached-mindfulness.yaml`
- Create: `packs/wellness-cbt/practices/A6-sar.yaml`
- Create: `packs/wellness-cbt/practices/C1-socratic.yaml`
- Create: `packs/wellness-cbt/practices/C2-decatastrophization.yaml`
- Create: `packs/wellness-cbt/practices/C3-behavioral-experiment.yaml`
- Create: `packs/wellness-cbt/practices/C5-double-standard.yaml`
- Create: `packs/wellness-cbt/practices/B1-behavioral-activation.yaml`
- Create: `packs/wellness-cbt/practices/U2-grounding.yaml`
- Test: `packages/telegram-bot/tests/test_practice_catalog.py`

Write each YAML file following the schema from the design doc (see Task 8 for U2 example). Each must include all steps with full fallback keys, proper button actions, and outcome schema.

**Test:** Validate all 12 practices load without error:

```python
# tests/test_practice_catalog.py
"""Test that all v1 practice YAML files pass validation."""
import pytest
from pathlib import Path
from wellness_bot.protocol.practice_loader import PracticeLoader

PRACTICES_DIR = Path(__file__).parent.parent.parent.parent.parent / "packs" / "wellness-cbt" / "practices"


class TestPracticeCatalog:
    @pytest.fixture
    def loader(self):
        assert PRACTICES_DIR.exists(), f"Practices dir not found: {PRACTICES_DIR}"
        return PracticeLoader(practices_dir=PRACTICES_DIR)

    def test_all_12_practices_load(self, loader):
        practices = loader.load_all()
        expected_ids = {"M2", "M3", "A1", "A2", "A3", "A6", "C1", "C2", "C3", "C5", "B1", "U2"}
        assert set(practices.keys()) == expected_ids

    def test_all_have_steps(self, loader):
        for pid, p in loader.load_all().items():
            assert len(p.steps) >= 1, f"{pid} has no steps"

    def test_all_steps_have_fallbacks(self, loader):
        for pid, p in loader.load_all().items():
            for step in p.steps:
                assert "user_confused" in step.fallback, f"{pid} step {step.index} missing user_confused"
                assert "cannot_now" in step.fallback, f"{pid} step {step.index} missing cannot_now"
                assert "too_hard" in step.fallback, f"{pid} step {step.index} missing too_hard"

    def test_step_indices_continuous(self, loader):
        for pid, p in loader.load_all().items():
            indices = [s.index for s in p.steps]
            assert indices == list(range(1, len(indices) + 1)), f"{pid} has non-continuous indices"

    def test_priority_ranks_unique(self, loader):
        practices = loader.load_all()
        ranks = [p.priority_rank for p in practices.values()]
        assert len(ranks) == len(set(ranks)), "Duplicate priority_rank found"
```

**Commit:**

```bash
git add packs/wellness-cbt/practices/ packages/telegram-bot/tests/test_practice_catalog.py
git commit -m "feat(protocol): add 12 practice YAML files for v1 catalog"
```

---

## Phase 6: LLM Adapter

### Task 10: Create LLM Adapter with response validation

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/llm_adapter.py`
- Test: `packages/telegram-bot/tests/test_llm_adapter.py`

Implement `LLMAdapter` class with:
- `generate(contract: LLMContract) -> str` — builds system prompt, calls LLM, validates response
- `ResponseValidator` with all 9 checks from design (length, must_include, must_not, no_diagnosis, no_medication, language, state_alignment, actionability, safety_lexicon)
- Circuit breaker (3 failures in 60s → templates)
- State-specific fallbacks
- max_repeat_count = 2

Follow TDD: write tests with mocked LLM, then implement.

**Commit:**

```bash
git commit -m "feat(protocol): add LLM adapter with contract-bound generation and validation"
```

---

## Phase 7: Integration

### Task 11: Wire protocol engine into Telegram handlers

**Files:**
- Modify: `packages/telegram-bot/src/wellness_bot/handlers.py`
- Modify: `packages/telegram-bot/src/wellness_bot/app.py`
- Modify: `packages/telegram-bot/src/wellness_bot/session_store.py` (add schema init)
- Test: `packages/telegram-bot/tests/test_protocol_integration.py`

Wire the pipeline: Handler → SafetyClassifier → ProtocolEngine → RuleEngine → PracticeRunner → LLM Adapter → ProgressTracker. Add per-user lock. Add idempotency check. Integrate with existing `WellnessBot` class.

**Commit:**

```bash
git commit -m "feat(protocol): wire protocol engine into Telegram handlers"
```

---

### Task 12: Add inline keyboard support for practice steps

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/telegram_ui.py`
- Modify: `packages/telegram-bot/src/wellness_bot/handlers.py` (add callback handler)
- Test: `packages/telegram-bot/tests/test_telegram_ui.py`

Implement Telegram inline keyboard builder from practice YAML button definitions. Add callback query handler for button presses. Route callbacks through protocol engine.

**Commit:**

```bash
git commit -m "feat(protocol): add Telegram inline keyboard support for practice steps"
```

---

## Phase 8: End-to-End Testing

### Task 13: Integration tests for full protocol flow

**Files:**
- Create: `packages/telegram-bot/tests/test_protocol_e2e.py`

Write end-to-end tests covering:
1. New user flow: INTAKE → FORMULATION → GOAL → MODULE_SELECT → PRACTICE → REFLECTION → HOMEWORK → SESSION_END
2. Returning user flow: skips INTAKE
3. Crisis flow: SAFETY → ESCALATION → SESSION_END
4. Resume flow: incomplete practice → resume from checkpoint
5. Timeout flow: no response → SESSION_END
6. CAUTION_ELEVATED: blocks exposure techniques

**Commit:**

```bash
git commit -m "test(protocol): add end-to-end tests for protocol flows"
```

---

### Task 14: Run full test suite and fix any issues

**Run:**

```bash
cd packages/telegram-bot && python3 -m pytest tests/ -v --tb=short
```

Fix any failures. Ensure all existing tests (31) still pass alongside new protocol tests.

**Commit:**

```bash
git commit -m "fix(protocol): resolve test suite issues from integration"
```
