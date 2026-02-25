# Proactive Coaching Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the wellness Telegram bot from a rigid FSM with hardcoded Russian into a multilingual proactive coaching bot with deterministic safety gates, LLM-driven context analysis, and adaptive practice suggestions.

**Architecture:** 11-step pipeline: Safety Gate → Language Resolver → Context Analyzer (LLM) → Opportunity Scorer → Practice Selector → Coach Policy Engine → Response Generator → Output Safety Check → Consent Gate → FSM Orchestrator → Audit & Metrics. Two-level FSM: Conversation FSM (FREE_CHAT, EXPLORE, PRACTICE_OFFERED, PRACTICE_ACTIVE, PRACTICE_PAUSED, FOLLOW_UP, CRISIS) and Practice FSM (CONSENT, BASELINE, STEP_n, CHECKPOINT, ADAPT, WRAP_UP, FOLLOW_UP).

**Tech Stack:** Python 3.12, aiogram 3.4, aiosqlite, Anthropic Claude API, Pydantic v2, pytest-asyncio.

**Design doc:** `docs/plans/2026-02-25-proactive-coaching-bot-design.md`

---

## Task 1: New type definitions and enums

Replace the old `DialogueState` enum and add new types for the 2-level FSM, context analysis, and coaching pipeline.

**Files:**
- Modify: `packages/telegram-bot/src/wellness_bot/protocol/types.py`
- Test: `packages/telegram-bot/tests/test_new_types.py`

**Step 1: Write the failing test**

```python
# tests/test_new_types.py
import pytest
from wellness_bot.protocol.types import (
    ConversationState, PracticeState, CoachingDecision,
    EmotionalState, ContextState, OpportunityResult,
    PracticeCandidateRanked, CoachDecision, ConsentStatus,
)


def test_conversation_states_exist():
    assert ConversationState.FREE_CHAT.value == "free_chat"
    assert ConversationState.EXPLORE.value == "explore"
    assert ConversationState.PRACTICE_OFFERED.value == "practice_offered"
    assert ConversationState.PRACTICE_ACTIVE.value == "practice_active"
    assert ConversationState.PRACTICE_PAUSED.value == "practice_paused"
    assert ConversationState.FOLLOW_UP.value == "follow_up"
    assert ConversationState.CRISIS.value == "crisis"


def test_practice_states_exist():
    assert PracticeState.CONSENT.value == "consent"
    assert PracticeState.BASELINE.value == "baseline"
    assert PracticeState.STEP.value == "step"
    assert PracticeState.CHECKPOINT.value == "checkpoint"
    assert PracticeState.ADAPT.value == "adapt"
    assert PracticeState.WRAP_UP.value == "wrap_up"
    assert PracticeState.FOLLOW_UP.value == "follow_up"


def test_coaching_decision_values():
    assert CoachingDecision.LISTEN.value == "listen"
    assert CoachingDecision.EXPLORE.value == "explore"
    assert CoachingDecision.SUGGEST.value == "suggest"
    assert CoachingDecision.GUIDE.value == "guide"
    assert CoachingDecision.ANSWER.value == "answer"


def test_emotional_state_creation():
    es = EmotionalState(anxiety=0.72, rumination=0.81, avoidance=0.33)
    assert es.anxiety == 0.72
    assert es.rumination == 0.81
    assert es.avoidance == 0.33
    assert es.perfectionism == 0.0  # default
    assert es.dominant == "rumination"


def test_emotional_state_dominant():
    es = EmotionalState(anxiety=0.9, rumination=0.1)
    assert es.dominant == "anxiety"


def test_context_state_creation():
    es = EmotionalState(anxiety=0.5)
    cs = ContextState(
        risk_level="low",
        emotional_state=es,
        readiness_for_practice=0.64,
        coaching_hypotheses=["thought_loop"],
        confidence=0.79,
        candidate_constraints=[],
    )
    assert cs.risk_level == "low"
    assert cs.confidence == 0.79


def test_opportunity_result():
    r = OpportunityResult(
        opportunity_score=0.74,
        allow_proactive_suggest=True,
        reason_codes=["repeated_anxiety_signals"],
    )
    assert r.opportunity_score == 0.74
    assert r.allow_proactive_suggest is True


def test_practice_candidate_ranked():
    p = PracticeCandidateRanked(
        practice_id="grounding_5_4_3_2_1",
        final_score=0.86,
        confidence=0.9,
        reason_codes=["high_anxiety", "short_duration"],
    )
    assert p.practice_id == "grounding_5_4_3_2_1"
    assert p.final_score == 0.86


def test_coach_decision():
    d = CoachDecision(
        decision=CoachingDecision.SUGGEST,
        selected_practice_id="grounding_5_4_3_2_1",
        style="warm_directive",
        must_ask_consent=True,
    )
    assert d.decision == CoachingDecision.SUGGEST
    assert d.must_ask_consent is True


def test_consent_status_values():
    assert ConsentStatus.PENDING.value == "pending"
    assert ConsentStatus.ACCEPTED.value == "accepted"
    assert ConsentStatus.DECLINED.value == "declined"
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_new_types.py -v`
Expected: FAIL — imports not found

**Step 3: Write minimal implementation**

Add the following to `packages/telegram-bot/src/wellness_bot/protocol/types.py` (append after existing code, keep old types for backward compat):

```python
# --- New types for proactive coaching bot ---

class ConversationState(str, Enum):
    FREE_CHAT = "free_chat"
    EXPLORE = "explore"
    PRACTICE_OFFERED = "practice_offered"
    PRACTICE_ACTIVE = "practice_active"
    PRACTICE_PAUSED = "practice_paused"
    FOLLOW_UP = "follow_up"
    CRISIS = "crisis"


class PracticeState(str, Enum):
    CONSENT = "consent"
    BASELINE = "baseline"
    STEP = "step"
    CHECKPOINT = "checkpoint"
    ADAPT = "adapt"
    WRAP_UP = "wrap_up"
    FOLLOW_UP = "follow_up"


class CoachingDecision(str, Enum):
    LISTEN = "listen"
    EXPLORE = "explore"
    SUGGEST = "suggest"
    GUIDE = "guide"
    ANSWER = "answer"


class ConsentStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


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
        return max(fields, key=fields.get)


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
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_new_types.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/types.py packages/telegram-bot/tests/test_new_types.py
git commit -m "feat(coaching): add new type definitions for 2-level FSM and coaching pipeline"
```

---

## Task 2: Database schema migration

Add new tables for the coaching bot: `user_profiles`, `decision_logs`, `practice_outcomes`, plus modify `sessions` and `messages` tables.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/protocol/schema_v2.py`
- Test: `packages/telegram-bot/tests/test_schema_v2.py`

**Step 1: Write the failing test**

```python
# tests/test_schema_v2.py
import pytest
import aiosqlite
from wellness_bot.protocol.schema_v2 import apply_coaching_schema, COACHING_SCHEMA


@pytest.fixture
async def db(tmp_path):
    path = str(tmp_path / "test.db")
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        await apply_coaching_schema(conn)
        yield conn


@pytest.mark.asyncio
async def test_users_table_exists(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='users'")
    row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_user_profiles_table_exists(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='user_profiles'")
    row = await cursor.fetchone()
    assert row is not None
    sql = row[0]
    assert "readiness_score" in sql
    assert "language_pref" in sql
    assert "preferred_style" in sql


@pytest.mark.asyncio
async def test_sessions_table_has_conversation_state(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='sessions'")
    row = await cursor.fetchone()
    assert "conversation_state" in row[0]
    assert "language" in row[0]


@pytest.mark.asyncio
async def test_messages_table_has_risk_level(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='messages'")
    row = await cursor.fetchone()
    assert "risk_level" in row[0]


@pytest.mark.asyncio
async def test_mood_entries_table(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='mood_entries'")
    row = await cursor.fetchone()
    assert "mood_score" in row[0]
    assert "stress_score" in row[0]


@pytest.mark.asyncio
async def test_practice_catalog_table(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='practice_catalog'")
    row = await cursor.fetchone()
    assert "contraindications" in row[0]
    assert "duration_min" in row[0]


@pytest.mark.asyncio
async def test_practice_runs_table(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='practice_runs'")
    row = await cursor.fetchone()
    assert "practice_id" in row[0]
    assert "state" in row[0]


@pytest.mark.asyncio
async def test_practice_run_events_table(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='practice_run_events'")
    row = await cursor.fetchone()
    assert "state_from" in row[0]
    assert "state_to" in row[0]


@pytest.mark.asyncio
async def test_practice_outcomes_table(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='practice_outcomes'")
    row = await cursor.fetchone()
    assert "baseline_mood" in row[0]
    assert "post_mood" in row[0]
    assert "self_report_effect" in row[0]


@pytest.mark.asyncio
async def test_decision_logs_table(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='decision_logs'")
    row = await cursor.fetchone()
    assert "context_state_json" in row[0]
    assert "opportunity_score" in row[0]
    assert "latency_ms" in row[0]


@pytest.mark.asyncio
async def test_safety_events_table(db):
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name='safety_events'")
    row = await cursor.fetchone()
    assert "severity" in row[0]
    assert "action" in row[0]


@pytest.mark.asyncio
async def test_schema_is_idempotent(db):
    await apply_coaching_schema(db)
    await apply_coaching_schema(db)
    cursor = await db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
    row = await cursor.fetchone()
    assert row[0] > 0


@pytest.mark.asyncio
async def test_indexes_created(db):
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
    rows = await cursor.fetchall()
    names = {r[0] for r in rows}
    assert "idx_messages_session_created" in names
    assert "idx_mood_entries_user_created" in names
    assert "idx_practice_outcomes_user_practice" in names
    assert "idx_decision_logs_session_created" in names
    assert "idx_safety_events_severity_created" in names
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_schema_v2.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/protocol/schema_v2.py
"""Database schema for the proactive coaching bot."""
from __future__ import annotations

import aiosqlite

COACHING_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    readiness_score REAL DEFAULT 0.5,
    preferred_style TEXT DEFAULT 'warm_supportive',
    language_pref TEXT,
    patterns_json TEXT DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    language TEXT NOT NULL DEFAULT 'ru',
    conversation_state TEXT NOT NULL DEFAULT 'free_chat',
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text TEXT NOT NULL,
    risk_level TEXT DEFAULT 'low',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mood_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    session_id TEXT REFERENCES sessions(id),
    mood_score REAL NOT NULL,
    stress_score REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS practice_catalog (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    targets TEXT NOT NULL DEFAULT '[]',
    contraindications TEXT NOT NULL DEFAULT '[]',
    duration_min INTEGER NOT NULL,
    duration_max INTEGER,
    protocol_yaml TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS practice_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    practice_id TEXT NOT NULL REFERENCES practice_catalog(id),
    step_order INTEGER NOT NULL,
    step_type TEXT NOT NULL,
    content TEXT NOT NULL,
    UNIQUE(practice_id, step_order)
);

CREATE TABLE IF NOT EXISTS practice_runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    session_id TEXT NOT NULL REFERENCES sessions(id),
    practice_id TEXT NOT NULL REFERENCES practice_catalog(id),
    state TEXT NOT NULL DEFAULT 'consent',
    current_step INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS practice_run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES practice_runs(id),
    state_from TEXT NOT NULL,
    state_to TEXT NOT NULL,
    event TEXT NOT NULL,
    payload_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS practice_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES practice_runs(id),
    baseline_mood REAL,
    post_mood REAL,
    self_report_effect REAL,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decision_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    context_state_json TEXT NOT NULL,
    decision TEXT NOT NULL,
    opportunity_score REAL,
    selected_practice_id TEXT,
    latency_ms INTEGER,
    cost REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS safety_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES sessions(id),
    detector TEXT NOT NULL,
    severity TEXT NOT NULL,
    action TEXT NOT NULL,
    message_hash TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_session_created ON messages(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mood_entries_user_created ON mood_entries(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_practice_outcomes_user_practice ON practice_outcomes(run_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decision_logs_session_created ON decision_logs(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_safety_events_severity_created ON safety_events(severity, created_at DESC);
"""


async def apply_coaching_schema(db: aiosqlite.Connection) -> None:
    """Apply the coaching bot schema idempotently."""
    await db.executescript(COACHING_SCHEMA)
    await db.commit()
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_schema_v2.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/protocol/schema_v2.py packages/telegram-bot/tests/test_schema_v2.py
git commit -m "feat(coaching): add v2 database schema for coaching bot"
```

---

## Task 3: Safety Gate (deterministic, multilingual)

Extend the existing `SafetyClassifier` with multilingual keyword lists. The safety gate runs before any LLM call and is deterministic.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/safety_gate.py`
- Test: `packages/telegram-bot/tests/test_safety_gate.py`

**Step 1: Write the failing test**

```python
# tests/test_safety_gate.py
import pytest
from wellness_bot.coaching.safety_gate import SafetyGate, SafetyGateResult


def test_safe_message_returns_safe():
    gate = SafetyGate()
    result = gate.check("Привет, как дела?")
    assert result.risk_level == "safe"
    assert result.safety_action == "pass"


def test_crisis_russian_self_harm():
    gate = SafetyGate()
    result = gate.check("хочу покончить с собой")
    assert result.risk_level == "crisis"
    assert result.safety_action == "crisis_protocol"
    assert len(result.signals) > 0


def test_crisis_english_self_harm():
    gate = SafetyGate()
    result = gate.check("I want to kill myself")
    assert result.risk_level == "crisis"
    assert result.safety_action == "crisis_protocol"


def test_crisis_spanish():
    gate = SafetyGate()
    result = gate.check("quiero suicidarme")
    assert result.risk_level == "crisis"


def test_violence_detected():
    gate = SafetyGate()
    result = gate.check("I want to hurt someone badly")
    assert result.risk_level == "crisis"


def test_safe_message_english():
    gate = SafetyGate()
    result = gate.check("I've been feeling a bit stressed lately")
    assert result.risk_level == "safe"


def test_safe_message_mixed_language():
    gate = SafetyGate()
    result = gate.check("Сегодня был хороший день, feeling great")
    assert result.risk_level == "safe"


def test_result_has_detector_field():
    gate = SafetyGate()
    result = gate.check("хочу покончить с собой")
    assert result.detector == "keyword_regex"


def test_empty_message_is_safe():
    gate = SafetyGate()
    result = gate.check("")
    assert result.risk_level == "safe"
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_safety_gate.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

First create the package directory:
```bash
mkdir -p packages/telegram-bot/src/wellness_bot/coaching
touch packages/telegram-bot/src/wellness_bot/coaching/__init__.py
```

```python
# packages/telegram-bot/src/wellness_bot/coaching/safety_gate.py
"""Deterministic multilingual safety gate. Runs BEFORE any LLM call."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SafetyGateResult:
    risk_level: str  # safe, medium, high, crisis
    safety_action: str  # pass, crisis_protocol, flag_review
    signals: list[str] = field(default_factory=list)
    detector: str = "keyword_regex"


# Each tuple: (compiled_regex, signal_name, risk_level)
_CRISIS_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Russian
    (re.compile(r"покончить\s*(с\s*собой|жизнь)", re.I), "self_harm_ru", "crisis"),
    (re.compile(r"суицид", re.I), "suicide_ru", "crisis"),
    (re.compile(r"(хочу|хотел[аи]?)\s*(умереть|сдохнуть|не\s*жить)", re.I), "death_wish_ru", "crisis"),
    (re.compile(r"повеситься|порезать\s*вены|прыгну\s*с", re.I), "method_ru", "crisis"),
    (re.compile(r"(убить|убью)\s*(себя)", re.I), "self_harm_direct_ru", "crisis"),
    (re.compile(r"не\s*вижу\s*смысла\s*(жить|в\s*жизни)", re.I), "hopelessness_ru", "high"),
    # English
    (re.compile(r"kill\s*(myself|me)", re.I), "self_harm_en", "crisis"),
    (re.compile(r"(want|going)\s*to\s*(die|end\s*(it|my\s*life))", re.I), "death_wish_en", "crisis"),
    (re.compile(r"suicid(e|al)", re.I), "suicide_en", "crisis"),
    (re.compile(r"(cut|hang|shoot|overdose)\s*(myself|me)", re.I), "method_en", "crisis"),
    (re.compile(r"no\s*reason\s*to\s*live", re.I), "hopelessness_en", "high"),
    # Spanish
    (re.compile(r"suicidarm[eE]", re.I), "suicide_es", "crisis"),
    (re.compile(r"quiero\s*morir(me)?", re.I), "death_wish_es", "crisis"),
    (re.compile(r"matarm[eE]", re.I), "self_harm_es", "crisis"),
    # Violence to others
    (re.compile(r"(убить|убью)\s+(его|её|их|человека|людей)", re.I), "violence_ru", "crisis"),
    (re.compile(r"(kill|hurt|harm)\s+(someone|him|her|them|people)\s*(bad|serious)?", re.I), "violence_en", "crisis"),
]


class SafetyGate:
    """Deterministic crisis screening. No LLM dependency."""

    def check(self, text: str) -> SafetyGateResult:
        if not text.strip():
            return SafetyGateResult(risk_level="safe", safety_action="pass")

        worst_risk = "safe"
        signals: list[str] = []

        for pattern, signal, risk in _CRISIS_PATTERNS:
            if pattern.search(text):
                signals.append(signal)
                if risk == "crisis":
                    worst_risk = "crisis"
                elif risk == "high" and worst_risk != "crisis":
                    worst_risk = "high"

        if worst_risk == "crisis":
            return SafetyGateResult(
                risk_level="crisis",
                safety_action="crisis_protocol",
                signals=signals,
            )
        elif worst_risk == "high":
            return SafetyGateResult(
                risk_level="high",
                safety_action="flag_review",
                signals=signals,
            )
        return SafetyGateResult(risk_level="safe", safety_action="pass")
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_safety_gate.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/ packages/telegram-bot/tests/test_safety_gate.py
git commit -m "feat(coaching): add deterministic multilingual safety gate"
```

---

## Task 4: Language Resolver

Detect language from user text, cache in session, override on explicit switch.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/language_resolver.py`
- Test: `packages/telegram-bot/tests/test_language_resolver.py`

**Step 1: Write the failing test**

```python
# tests/test_language_resolver.py
import pytest
from wellness_bot.coaching.language_resolver import LanguageResolver


def test_detect_russian():
    resolver = LanguageResolver()
    assert resolver.detect("Привет, как дела?") == "ru"


def test_detect_english():
    resolver = LanguageResolver()
    assert resolver.detect("Hello, how are you?") == "en"


def test_detect_spanish():
    resolver = LanguageResolver()
    assert resolver.detect("Hola, ¿cómo estás?") == "es"


def test_detect_mixed_defaults_to_dominant():
    resolver = LanguageResolver()
    lang = resolver.detect("Привет hello мир world ещё текст")
    assert lang == "ru"  # more Cyrillic chars


def test_cache_returns_previous():
    resolver = LanguageResolver()
    resolver.resolve("user1", "Привет!")
    # Short ambiguous message — should use cached
    result = resolver.resolve("user1", "ok")
    assert result == "ru"


def test_override_on_explicit_switch():
    resolver = LanguageResolver()
    resolver.resolve("user1", "Привет!")
    assert resolver.resolve("user1", "Let me switch to English for this conversation") == "en"


def test_empty_message_returns_cached_or_default():
    resolver = LanguageResolver()
    assert resolver.resolve("user1", "") == "en"  # default


def test_resolve_returns_detected_language():
    resolver = LanguageResolver()
    result = resolver.resolve("user1", "Сегодня хороший день")
    assert result == "ru"
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_language_resolver.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/coaching/language_resolver.py
"""Language detection with session caching."""
from __future__ import annotations

import re
import unicodedata


_SCRIPT_RANGES = {
    "ru": re.compile(r"[\u0400-\u04FF]"),  # Cyrillic
    "en": re.compile(r"[A-Za-z]"),  # Latin
    "ar": re.compile(r"[\u0600-\u06FF]"),  # Arabic
    "zh": re.compile(r"[\u4E00-\u9FFF]"),  # CJK
    "ja": re.compile(r"[\u3040-\u30FF]"),  # Hiragana + Katakana
    "ko": re.compile(r"[\uAC00-\uD7AF]"),  # Hangul
    "he": re.compile(r"[\u0590-\u05FF]"),  # Hebrew
}

_LATIN_HINTS = {
    "es": re.compile(r"\b(hola|cómo|estás|gracias|quiero|puedo|tengo|bueno)\b", re.I),
    "fr": re.compile(r"\b(bonjour|comment|merci|je suis|oui|non|très)\b", re.I),
    "de": re.compile(r"\b(hallo|danke|ich bin|wie|bitte|guten)\b", re.I),
    "pt": re.compile(r"\b(olá|obrigad[oa]|como|estou|bom|muito)\b", re.I),
}

# Minimum chars to attempt detection (below this, use cache)
_MIN_DETECT_CHARS = 4


class LanguageResolver:
    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def detect(self, text: str) -> str:
        """Detect language from text. Returns ISO 639-1 code."""
        if not text.strip():
            return "en"

        counts: dict[str, int] = {}
        for lang, pattern in _SCRIPT_RANGES.items():
            n = len(pattern.findall(text))
            if n > 0:
                counts[lang] = n

        if not counts:
            return "en"

        dominant = max(counts, key=counts.get)

        # If Latin-dominant, try to identify specific language
        if dominant == "en":
            for lang, hint in _LATIN_HINTS.items():
                if hint.search(text):
                    return lang

        return dominant

    def resolve(self, user_id: str, text: str) -> str:
        """Detect language, use cache for short/ambiguous messages."""
        stripped = text.strip()

        if len(stripped) < _MIN_DETECT_CHARS:
            return self._cache.get(user_id, "en")

        detected = self.detect(stripped)
        self._cache[user_id] = detected
        return detected

    def get_cached(self, user_id: str) -> str | None:
        return self._cache.get(user_id)

    def set_language(self, user_id: str, language: str) -> None:
        self._cache[user_id] = language
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_language_resolver.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/language_resolver.py packages/telegram-bot/tests/test_language_resolver.py
git commit -m "feat(coaching): add language resolver with session caching"
```

---

## Task 5: Context Analyzer (LLM)

LLM-based analysis of user state from dialogue + DB history. Returns structured `ContextState`.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/context_analyzer.py`
- Test: `packages/telegram-bot/tests/test_context_analyzer.py`

**Step 1: Write the failing test**

```python
# tests/test_context_analyzer.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from wellness_bot.coaching.context_analyzer import ContextAnalyzer
from wellness_bot.protocol.types import EmotionalState, ContextState


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.chat = AsyncMock(return_value=MagicMock(
        content='{"risk_level":"low","emotional_state":{"anxiety":0.7,"rumination":0.8,"avoidance":0.1},'
                '"readiness_for_practice":0.6,"coaching_hypotheses":["thought_loop"],'
                '"confidence":0.85,"candidate_constraints":[]}',
        input_tokens=100,
        output_tokens=50,
    ))
    return provider


@pytest.mark.asyncio
async def test_analyze_returns_context_state(mock_provider):
    analyzer = ContextAnalyzer(llm_provider=mock_provider)
    result = await analyzer.analyze(
        user_message="Я снова весь день думаю о том что сказал на работе",
        dialogue_window=[],
        mood_history=[],
        practice_history=[],
        user_profile={},
        language="ru",
    )
    assert isinstance(result, ContextState)
    assert result.risk_level == "low"
    assert result.emotional_state.rumination == 0.8
    assert result.confidence == 0.85


@pytest.mark.asyncio
async def test_analyze_calls_llm_with_system_prompt(mock_provider):
    analyzer = ContextAnalyzer(llm_provider=mock_provider)
    await analyzer.analyze(
        user_message="test",
        dialogue_window=[],
        mood_history=[],
        practice_history=[],
        user_profile={},
        language="en",
    )
    mock_provider.chat.assert_called_once()
    call_kwargs = mock_provider.chat.call_args
    assert "context" in call_kwargs.kwargs.get("system", "").lower() or \
           "context" in str(call_kwargs.args).lower()


@pytest.mark.asyncio
async def test_analyze_handles_malformed_json(mock_provider):
    mock_provider.chat.return_value = MagicMock(
        content="not valid json at all",
        input_tokens=100,
        output_tokens=50,
    )
    analyzer = ContextAnalyzer(llm_provider=mock_provider)
    result = await analyzer.analyze(
        user_message="hello",
        dialogue_window=[],
        mood_history=[],
        practice_history=[],
        user_profile={},
        language="en",
    )
    # Should return safe defaults, not crash
    assert result.risk_level == "low"
    assert result.confidence < 0.5


@pytest.mark.asyncio
async def test_analyze_includes_mood_history_in_prompt(mock_provider):
    analyzer = ContextAnalyzer(llm_provider=mock_provider)
    await analyzer.analyze(
        user_message="test",
        dialogue_window=[],
        mood_history=[{"date": "2026-02-20", "mood": 3}],
        practice_history=[],
        user_profile={},
        language="ru",
    )
    call_args = str(mock_provider.chat.call_args)
    assert "mood" in call_args.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_context_analyzer.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/coaching/context_analyzer.py
"""LLM-based context analysis. Returns structured ContextState."""
from __future__ import annotations

import json
import logging

from wellness_bot.protocol.types import ContextState, EmotionalState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a context analyzer for a wellness coaching bot. Analyze the user's message and conversation history to understand their emotional state and readiness for coaching.

Return a JSON object with EXACTLY these fields:
{
  "risk_level": "low" | "medium" | "high" | "crisis",
  "emotional_state": {
    "anxiety": 0.0-1.0,
    "rumination": 0.0-1.0,
    "avoidance": 0.0-1.0,
    "perfectionism": 0.0-1.0,
    "self_criticism": 0.0-1.0,
    "symptom_fixation": 0.0-1.0
  },
  "readiness_for_practice": 0.0-1.0,
  "coaching_hypotheses": ["string"],
  "confidence": 0.0-1.0,
  "candidate_constraints": ["string"]
}

Rules:
- Be conservative with risk_level. When in doubt, go higher.
- coaching_hypotheses: what patterns you observe (thought_loop, sleep_stress, social_anxiety, etc.)
- candidate_constraints: what to avoid (avoid_long_protocol, avoid_cognitive_load, etc.)
- Return ONLY valid JSON, no markdown, no explanation.
"""


def _build_user_prompt(
    user_message: str,
    dialogue_window: list[dict],
    mood_history: list[dict],
    practice_history: list[dict],
    user_profile: dict,
    language: str,
) -> str:
    parts = [f"User message: {user_message}", f"Language: {language}"]

    if dialogue_window:
        recent = dialogue_window[-10:]
        parts.append("Recent dialogue:")
        for msg in recent:
            parts.append(f"  {msg.get('role', '?')}: {msg.get('text', '')[:200]}")

    if mood_history:
        parts.append(f"Mood history: {json.dumps(mood_history[-5:])}")

    if practice_history:
        parts.append(f"Practice history: {json.dumps(practice_history[-5:])}")

    if user_profile:
        parts.append(f"User profile: {json.dumps(user_profile)}")

    return "\n".join(parts)


def _parse_response(text: str) -> ContextState:
    """Parse LLM JSON response into ContextState. Returns safe defaults on failure."""
    try:
        data = json.loads(text.strip())
        es_raw = data.get("emotional_state", {})
        emotional_state = EmotionalState(
            anxiety=float(es_raw.get("anxiety", 0.0)),
            rumination=float(es_raw.get("rumination", 0.0)),
            avoidance=float(es_raw.get("avoidance", 0.0)),
            perfectionism=float(es_raw.get("perfectionism", 0.0)),
            self_criticism=float(es_raw.get("self_criticism", 0.0)),
            symptom_fixation=float(es_raw.get("symptom_fixation", 0.0)),
        )
        return ContextState(
            risk_level=data.get("risk_level", "low"),
            emotional_state=emotional_state,
            readiness_for_practice=float(data.get("readiness_for_practice", 0.5)),
            coaching_hypotheses=data.get("coaching_hypotheses", []),
            confidence=float(data.get("confidence", 0.5)),
            candidate_constraints=data.get("candidate_constraints", []),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning("Failed to parse context analyzer response: %s", e)
        return ContextState(
            risk_level="low",
            emotional_state=EmotionalState(),
            readiness_for_practice=0.5,
            coaching_hypotheses=[],
            confidence=0.3,
            candidate_constraints=[],
        )


class ContextAnalyzer:
    def __init__(self, llm_provider, model: str = "claude-haiku-4-5-20251001") -> None:
        self._provider = llm_provider
        self._model = model

    async def analyze(
        self,
        user_message: str,
        dialogue_window: list[dict],
        mood_history: list[dict],
        practice_history: list[dict],
        user_profile: dict,
        language: str,
    ) -> ContextState:
        user_prompt = _build_user_prompt(
            user_message, dialogue_window, mood_history,
            practice_history, user_profile, language,
        )
        try:
            response = await self._provider.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system=_SYSTEM_PROMPT,
                model=self._model,
            )
            return _parse_response(response.content)
        except Exception as e:
            logger.exception("Context analyzer LLM call failed: %s", e)
            return ContextState(
                risk_level="low",
                emotional_state=EmotionalState(),
                readiness_for_practice=0.5,
                coaching_hypotheses=[],
                confidence=0.2,
                candidate_constraints=[],
            )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_context_analyzer.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/context_analyzer.py packages/telegram-bot/tests/test_context_analyzer.py
git commit -m "feat(coaching): add LLM-based context analyzer"
```

---

## Task 6: Opportunity Scorer

Scores whether it's appropriate to proactively suggest a practice. Uses cooldowns, refusal history, and context state.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/opportunity_scorer.py`
- Test: `packages/telegram-bot/tests/test_opportunity_scorer.py`

**Step 1: Write the failing test**

```python
# tests/test_opportunity_scorer.py
import pytest
from datetime import datetime, timedelta
from wellness_bot.coaching.opportunity_scorer import OpportunityScorer
from wellness_bot.protocol.types import ContextState, EmotionalState, OpportunityResult


def _make_context(anxiety=0.5, rumination=0.5, confidence=0.8, risk="low") -> ContextState:
    return ContextState(
        risk_level=risk,
        emotional_state=EmotionalState(anxiety=anxiety, rumination=rumination),
        readiness_for_practice=0.6,
        coaching_hypotheses=["thought_loop"],
        confidence=confidence,
        candidate_constraints=[],
    )


def test_high_anxiety_scores_high():
    scorer = OpportunityScorer()
    result = scorer.score(
        context=_make_context(anxiety=0.9, rumination=0.8),
        recent_suggestions=[],
        messages_since_last_suggest=5,
    )
    assert result.opportunity_score >= 0.6
    assert result.allow_proactive_suggest is True


def test_low_signal_scores_low():
    scorer = OpportunityScorer()
    result = scorer.score(
        context=_make_context(anxiety=0.1, rumination=0.1),
        recent_suggestions=[],
        messages_since_last_suggest=5,
    )
    assert result.opportunity_score < 0.6
    assert result.allow_proactive_suggest is False


def test_cooldown_after_two_declines():
    scorer = OpportunityScorer()
    now = datetime.utcnow()
    result = scorer.score(
        context=_make_context(anxiety=0.9),
        recent_suggestions=[
            {"ts": (now - timedelta(hours=1)).isoformat(), "accepted": False},
            {"ts": (now - timedelta(minutes=30)).isoformat(), "accepted": False},
        ],
        messages_since_last_suggest=5,
    )
    assert result.allow_proactive_suggest is False


def test_too_few_messages_blocks_suggest():
    scorer = OpportunityScorer()
    result = scorer.score(
        context=_make_context(anxiety=0.9),
        recent_suggestions=[],
        messages_since_last_suggest=1,  # less than 3
    )
    assert result.allow_proactive_suggest is False


def test_crisis_blocks_suggest():
    scorer = OpportunityScorer()
    result = scorer.score(
        context=_make_context(risk="crisis"),
        recent_suggestions=[],
        messages_since_last_suggest=10,
    )
    assert result.allow_proactive_suggest is False


def test_accepted_suggestion_resets_decline_count():
    scorer = OpportunityScorer()
    now = datetime.utcnow()
    result = scorer.score(
        context=_make_context(anxiety=0.8),
        recent_suggestions=[
            {"ts": (now - timedelta(hours=2)).isoformat(), "accepted": False},
            {"ts": (now - timedelta(hours=1)).isoformat(), "accepted": True},
        ],
        messages_since_last_suggest=5,
    )
    # Last suggestion was accepted, so no cooldown
    assert result.allow_proactive_suggest is True
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_opportunity_scorer.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/coaching/opportunity_scorer.py
"""Proactive opportunity scoring with cooldowns."""
from __future__ import annotations

from datetime import datetime, timedelta

from wellness_bot.protocol.types import ContextState, OpportunityResult

# Policy constants
MIN_MESSAGES_BETWEEN_SUGGESTS = 3
MAX_CONSECUTIVE_DECLINES = 2
COOLDOWN_HOURS_AFTER_DECLINES = 24
OPPORTUNITY_THRESHOLD = 0.60


class OpportunityScorer:
    def score(
        self,
        context: ContextState,
        recent_suggestions: list[dict],
        messages_since_last_suggest: int,
    ) -> OpportunityResult:
        # Crisis: no proactive suggestions
        if context.risk_level in ("high", "crisis"):
            return OpportunityResult(
                opportunity_score=0.0,
                allow_proactive_suggest=False,
                reason_codes=["risk_level_too_high"],
            )

        # Too few messages since last suggestion
        if messages_since_last_suggest < MIN_MESSAGES_BETWEEN_SUGGESTS:
            return OpportunityResult(
                opportunity_score=0.0,
                allow_proactive_suggest=False,
                reason_codes=["too_few_messages"],
            )

        # Check consecutive declines (count from most recent backwards)
        consecutive_declines = 0
        for s in reversed(recent_suggestions):
            if s.get("accepted"):
                break
            consecutive_declines += 1

        if consecutive_declines >= MAX_CONSECUTIVE_DECLINES:
            return OpportunityResult(
                opportunity_score=0.0,
                allow_proactive_suggest=False,
                reason_codes=["consecutive_declines_cooldown"],
                cooldown_until=(datetime.utcnow() + timedelta(hours=COOLDOWN_HOURS_AFTER_DECLINES)).isoformat(),
            )

        # Score based on emotional signals
        es = context.emotional_state
        signal_strength = max(es.anxiety, es.rumination, es.avoidance, es.self_criticism)
        readiness = context.readiness_for_practice
        confidence = context.confidence

        score = (
            0.45 * signal_strength
            + 0.30 * readiness
            + 0.25 * confidence
        )
        score = min(max(score, 0.0), 1.0)

        reason_codes = []
        if signal_strength > 0.6:
            reason_codes.append("elevated_emotional_signals")
        if readiness > 0.5:
            reason_codes.append("user_appears_ready")

        return OpportunityResult(
            opportunity_score=round(score, 3),
            allow_proactive_suggest=score >= OPPORTUNITY_THRESHOLD,
            reason_codes=reason_codes,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_opportunity_scorer.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/opportunity_scorer.py packages/telegram-bot/tests/test_opportunity_scorer.py
git commit -m "feat(coaching): add proactive opportunity scorer with cooldowns"
```

---

## Task 7: Practice Selector (ranking with scoring formula)

Rank practices from the catalog using the design doc formula: `state_match * 0.35 + historical_effect * 0.25 + readiness_fit * 0.15 + duration_fit * 0.15 + novelty * 0.10 - penalties`.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/practice_selector.py`
- Test: `packages/telegram-bot/tests/test_practice_selector.py`

**Step 1: Write the failing test**

```python
# tests/test_practice_selector.py
import pytest
from wellness_bot.coaching.practice_selector import PracticeSelector, PracticeCatalogEntry
from wellness_bot.protocol.types import ContextState, EmotionalState, PracticeCandidateRanked


def _make_context(anxiety=0.8, rumination=0.5, readiness=0.6) -> ContextState:
    return ContextState(
        risk_level="low",
        emotional_state=EmotionalState(anxiety=anxiety, rumination=rumination),
        readiness_for_practice=readiness,
        coaching_hypotheses=["thought_loop"],
        confidence=0.8,
        candidate_constraints=[],
    )


def _sample_catalog() -> list[PracticeCatalogEntry]:
    return [
        PracticeCatalogEntry(
            id="U2", slug="grounding", title="5-4-3-2-1 Grounding",
            targets=["anxiety"], contraindications=[], duration_min=5,
        ),
        PracticeCatalogEntry(
            id="C1", slug="socratic", title="Socratic Questioning",
            targets=["rumination"], contraindications=[], duration_min=8,
        ),
        PracticeCatalogEntry(
            id="C3", slug="behavioral_experiment", title="Behavioral Experiment",
            targets=["avoidance"], contraindications=["high_distress"], duration_min=15,
        ),
    ]


def test_selector_returns_ranked_list():
    selector = PracticeSelector(catalog=_sample_catalog())
    results = selector.select(
        context=_make_context(anxiety=0.9),
        opportunity_score=0.8,
        user_history={},
        top_k=3,
    )
    assert len(results) > 0
    assert all(isinstance(r, PracticeCandidateRanked) for r in results)


def test_high_anxiety_ranks_grounding_first():
    selector = PracticeSelector(catalog=_sample_catalog())
    results = selector.select(
        context=_make_context(anxiety=0.9, rumination=0.1),
        opportunity_score=0.8,
        user_history={},
        top_k=3,
    )
    assert results[0].practice_id == "U2"


def test_high_rumination_ranks_socratic_first():
    selector = PracticeSelector(catalog=_sample_catalog())
    results = selector.select(
        context=_make_context(anxiety=0.1, rumination=0.9),
        opportunity_score=0.8,
        user_history={},
        top_k=3,
    )
    assert results[0].practice_id == "C1"


def test_contraindicated_practice_excluded():
    selector = PracticeSelector(catalog=_sample_catalog())
    results = selector.select(
        context=_make_context(anxiety=0.9),
        opportunity_score=0.8,
        user_history={},
        top_k=3,
        contraindications=["high_distress"],
    )
    ids = [r.practice_id for r in results]
    assert "C3" not in ids


def test_overuse_penalty_applied():
    selector = PracticeSelector(catalog=_sample_catalog())
    results = selector.select(
        context=_make_context(anxiety=0.9),
        opportunity_score=0.8,
        user_history={"U2": {"times_used_7d": 5, "avg_effectiveness": 0.7, "last_declined": False}},
        top_k=3,
    )
    # U2 should be penalized for overuse
    u2 = next(r for r in results if r.practice_id == "U2")
    assert u2.final_score < 0.9  # would be higher without penalty


def test_empty_catalog_returns_empty():
    selector = PracticeSelector(catalog=[])
    results = selector.select(
        context=_make_context(),
        opportunity_score=0.8,
        user_history={},
        top_k=3,
    )
    assert results == []


def test_results_sorted_by_score_desc():
    selector = PracticeSelector(catalog=_sample_catalog())
    results = selector.select(
        context=_make_context(),
        opportunity_score=0.8,
        user_history={},
        top_k=3,
    )
    scores = [r.final_score for r in results]
    assert scores == sorted(scores, reverse=True)
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_practice_selector.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/coaching/practice_selector.py
"""Practice ranking with weighted scoring formula."""
from __future__ import annotations

from dataclasses import dataclass, field

from wellness_bot.protocol.types import ContextState, PracticeCandidateRanked


@dataclass
class PracticeCatalogEntry:
    id: str
    slug: str
    title: str
    targets: list[str]
    contraindications: list[str]
    duration_min: int
    duration_max: int | None = None
    active: bool = True


# Weights from design doc
W_STATE_MATCH = 0.35
W_HISTORICAL = 0.25
W_READINESS = 0.15
W_DURATION = 0.15
W_NOVELTY = 0.10

# Penalty params
OVERUSE_THRESHOLD_7D = 2
OVERUSE_PENALTY_PER_USE = 0.08
DECLINE_PENALTY = 0.12


class PracticeSelector:
    def __init__(self, catalog: list[PracticeCatalogEntry]) -> None:
        self._catalog = [p for p in catalog if p.active]

    def select(
        self,
        context: ContextState,
        opportunity_score: float,
        user_history: dict,
        top_k: int = 3,
        contraindications: list[str] | None = None,
    ) -> list[PracticeCandidateRanked]:
        contraindications = contraindications or []

        # 1. Hard filter
        candidates = [
            p for p in self._catalog
            if not any(c in contraindications for c in p.contraindications)
        ]

        if not candidates:
            return []

        # 2-3. Score each candidate
        scored: list[PracticeCandidateRanked] = []
        es = context.emotional_state

        for p in candidates:
            # state_match: how well practice targets match emotional state
            state_match = self._calc_state_match(p.targets, es)

            # historical_effect from user history
            hist = user_history.get(p.id, {})
            historical = hist.get("avg_effectiveness", 0.5)

            # readiness_fit
            readiness_fit = context.readiness_for_practice

            # duration_fit: shorter practices score higher when distressed
            max_signal = max(es.anxiety, es.rumination, es.avoidance)
            if max_signal > 0.7:
                duration_fit = 1.0 if p.duration_min <= 10 else 0.4
            else:
                duration_fit = 0.7

            # novelty: inverse of usage count
            times_7d = hist.get("times_used_7d", 0)
            novelty = max(0.0, 1.0 - times_7d * 0.2)

            base_score = (
                W_STATE_MATCH * state_match
                + W_HISTORICAL * historical
                + W_READINESS * readiness_fit
                + W_DURATION * duration_fit
                + W_NOVELTY * novelty
            )

            # Penalties
            overuse_penalty = max(0, times_7d - OVERUSE_THRESHOLD_7D) * OVERUSE_PENALTY_PER_USE
            decline_penalty = DECLINE_PENALTY if hist.get("last_declined") else 0.0
            penalty = overuse_penalty + decline_penalty

            final = max(0.0, min(1.0, base_score - penalty))

            reason_codes = []
            if state_match > 0.5:
                reason_codes.append(f"matches_{es.dominant}")
            if historical > 0.6:
                reason_codes.append("worked_before")
            if p.duration_min <= 5:
                reason_codes.append("short_duration")

            scored.append(PracticeCandidateRanked(
                practice_id=p.id,
                final_score=round(final, 3),
                confidence=context.confidence,
                reason_codes=reason_codes,
            ))

        # 4-6. Sort and return top_k
        scored.sort(key=lambda x: x.final_score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _calc_state_match(targets: list[str], es) -> float:
        if not targets:
            return 0.3
        scores = {
            "anxiety": es.anxiety,
            "rumination": es.rumination,
            "avoidance": es.avoidance,
            "perfectionism": es.perfectionism,
            "self_criticism": es.self_criticism,
            "symptom_fixation": es.symptom_fixation,
        }
        matched = [scores.get(t, 0.0) for t in targets]
        return max(matched) if matched else 0.3
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_practice_selector.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/practice_selector.py packages/telegram-bot/tests/test_practice_selector.py
git commit -m "feat(coaching): add practice selector with weighted scoring formula"
```

---

## Task 8: Coach Policy Engine

Makes the final coaching decision: listen, explore, suggest, guide, or answer.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/coach_policy.py`
- Test: `packages/telegram-bot/tests/test_coach_policy.py`

**Step 1: Write the failing test**

```python
# tests/test_coach_policy.py
import pytest
from wellness_bot.coaching.coach_policy import CoachPolicyEngine
from wellness_bot.protocol.types import (
    ContextState, EmotionalState, OpportunityResult,
    PracticeCandidateRanked, CoachDecision, CoachingDecision,
)


def _ctx(risk="low", confidence=0.8, readiness=0.6, anxiety=0.5) -> ContextState:
    return ContextState(
        risk_level=risk,
        emotional_state=EmotionalState(anxiety=anxiety),
        readiness_for_practice=readiness,
        coaching_hypotheses=[],
        confidence=confidence,
        candidate_constraints=[],
    )


def _opp(score=0.8, allow=True) -> OpportunityResult:
    return OpportunityResult(opportunity_score=score, allow_proactive_suggest=allow, reason_codes=[])


def _practices(score=0.8) -> list[PracticeCandidateRanked]:
    return [PracticeCandidateRanked(practice_id="U2", final_score=score, confidence=0.9, reason_codes=[])]


def test_suggest_when_opportunity_high_and_practice_strong():
    engine = CoachPolicyEngine()
    result = engine.decide(_ctx(), _opp(score=0.8), _practices(score=0.8))
    assert result.decision == CoachingDecision.SUGGEST
    assert result.selected_practice_id == "U2"
    assert result.must_ask_consent is True


def test_listen_when_opportunity_blocked():
    engine = CoachPolicyEngine()
    result = engine.decide(_ctx(), _opp(score=0.3, allow=False), _practices())
    assert result.decision in (CoachingDecision.LISTEN, CoachingDecision.EXPLORE)


def test_explore_when_low_confidence():
    engine = CoachPolicyEngine()
    result = engine.decide(_ctx(confidence=0.4), _opp(score=0.7), _practices(score=0.5))
    assert result.decision == CoachingDecision.EXPLORE


def test_crisis_forces_listen():
    engine = CoachPolicyEngine()
    result = engine.decide(_ctx(risk="crisis"), _opp(score=0.9), _practices())
    assert result.decision == CoachingDecision.LISTEN
    assert result.selected_practice_id is None


def test_answer_when_no_emotional_signal():
    engine = CoachPolicyEngine()
    ctx = _ctx(anxiety=0.05)
    ctx.coaching_hypotheses = []
    result = engine.decide(ctx, _opp(score=0.2, allow=False), [])
    assert result.decision == CoachingDecision.ANSWER
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_coach_policy.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/coaching/coach_policy.py
"""Coach Policy Engine: decides coaching strategy."""
from __future__ import annotations

from wellness_bot.protocol.types import (
    ContextState, OpportunityResult, PracticeCandidateRanked,
    CoachDecision, CoachingDecision,
)

# Thresholds from design doc
SUGGEST_SCORE_THRESHOLD = 0.58
EXPLORE_CONFIDENCE_THRESHOLD = 0.5


class CoachPolicyEngine:
    def decide(
        self,
        context: ContextState,
        opportunity: OpportunityResult,
        ranked_practices: list[PracticeCandidateRanked],
    ) -> CoachDecision:
        # Crisis: always listen, no practice suggestions
        if context.risk_level in ("high", "crisis"):
            return CoachDecision(
                decision=CoachingDecision.LISTEN,
                style="warm_supportive",
            )

        # No emotional signal and no practices: answer mode
        es = context.emotional_state
        max_signal = max(es.anxiety, es.rumination, es.avoidance,
                         es.perfectionism, es.self_criticism, es.symptom_fixation)
        if max_signal < 0.15 and not ranked_practices:
            return CoachDecision(
                decision=CoachingDecision.ANSWER,
                style="direct_helpful",
            )

        # Low confidence: explore first
        if context.confidence < EXPLORE_CONFIDENCE_THRESHOLD:
            return CoachDecision(
                decision=CoachingDecision.EXPLORE,
                style="warm_curious",
            )

        # Opportunity not allowed: listen or explore
        if not opportunity.allow_proactive_suggest:
            decision = CoachingDecision.EXPLORE if max_signal > 0.4 else CoachingDecision.LISTEN
            return CoachDecision(decision=decision, style="warm_supportive")

        # Check if top practice is strong enough to suggest
        if ranked_practices and ranked_practices[0].final_score >= SUGGEST_SCORE_THRESHOLD:
            top = ranked_practices[0]
            return CoachDecision(
                decision=CoachingDecision.SUGGEST,
                selected_practice_id=top.practice_id,
                style="warm_directive",
                must_ask_consent=True,
            )

        # Guide: there are signals but no strong practice match
        if max_signal > 0.3:
            return CoachDecision(
                decision=CoachingDecision.GUIDE,
                style="warm_curious",
            )

        return CoachDecision(
            decision=CoachingDecision.LISTEN,
            style="warm_supportive",
        )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_coach_policy.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/coach_policy.py packages/telegram-bot/tests/test_coach_policy.py
git commit -m "feat(coaching): add coach policy engine with decision logic"
```

---

## Task 9: Conversation FSM Orchestrator

2-level FSM with Conversation states and Practice states. Manages transitions with guards.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/fsm.py`
- Test: `packages/telegram-bot/tests/test_coaching_fsm.py`

**Step 1: Write the failing test**

```python
# tests/test_coaching_fsm.py
import pytest
from wellness_bot.coaching.fsm import ConversationFSM
from wellness_bot.protocol.types import ConversationState, PracticeState, CoachingDecision


def test_initial_state_is_free_chat():
    fsm = ConversationFSM()
    assert fsm.conversation_state == ConversationState.FREE_CHAT
    assert fsm.practice_state is None


def test_free_chat_to_explore():
    fsm = ConversationFSM()
    assert fsm.transition(CoachingDecision.EXPLORE) is True
    assert fsm.conversation_state == ConversationState.EXPLORE


def test_free_chat_to_practice_offered():
    fsm = ConversationFSM()
    assert fsm.transition(CoachingDecision.SUGGEST) is True
    assert fsm.conversation_state == ConversationState.PRACTICE_OFFERED


def test_practice_offered_accept():
    fsm = ConversationFSM()
    fsm.transition(CoachingDecision.SUGGEST)
    assert fsm.accept_practice() is True
    assert fsm.conversation_state == ConversationState.PRACTICE_ACTIVE
    assert fsm.practice_state == PracticeState.CONSENT


def test_practice_offered_decline():
    fsm = ConversationFSM()
    fsm.transition(CoachingDecision.SUGGEST)
    assert fsm.decline_practice() is True
    assert fsm.conversation_state == ConversationState.FREE_CHAT


def test_practice_active_to_paused():
    fsm = ConversationFSM()
    fsm.transition(CoachingDecision.SUGGEST)
    fsm.accept_practice()
    assert fsm.pause_practice() is True
    assert fsm.conversation_state == ConversationState.PRACTICE_PAUSED


def test_practice_paused_to_active():
    fsm = ConversationFSM()
    fsm.transition(CoachingDecision.SUGGEST)
    fsm.accept_practice()
    fsm.pause_practice()
    assert fsm.resume_practice() is True
    assert fsm.conversation_state == ConversationState.PRACTICE_ACTIVE


def test_crisis_from_any_state():
    for starting_state in [ConversationState.FREE_CHAT, ConversationState.EXPLORE, ConversationState.PRACTICE_ACTIVE]:
        fsm = ConversationFSM()
        fsm._conversation_state = starting_state
        assert fsm.enter_crisis() is True
        assert fsm.conversation_state == ConversationState.CRISIS


def test_crisis_stabilized():
    fsm = ConversationFSM()
    fsm.enter_crisis()
    assert fsm.stabilize_from_crisis() is True
    assert fsm.conversation_state == ConversationState.FREE_CHAT


def test_practice_fsm_step_advance():
    fsm = ConversationFSM()
    fsm.transition(CoachingDecision.SUGGEST)
    fsm.accept_practice()
    # Move through practice FSM
    assert fsm.advance_practice_step("baseline") is True
    assert fsm.practice_state == PracticeState.BASELINE
    assert fsm.advance_practice_step("step") is True
    assert fsm.practice_state == PracticeState.STEP


def test_practice_completion():
    fsm = ConversationFSM()
    fsm.transition(CoachingDecision.SUGGEST)
    fsm.accept_practice()
    assert fsm.complete_practice() is True
    assert fsm.conversation_state == ConversationState.FOLLOW_UP
    assert fsm.practice_state is None


def test_invalid_transition_returns_false():
    fsm = ConversationFSM()
    # Can't accept practice when in FREE_CHAT
    assert fsm.accept_practice() is False
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_coaching_fsm.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/coaching/fsm.py
"""2-level FSM: Conversation FSM + Practice FSM."""
from __future__ import annotations

from wellness_bot.protocol.types import ConversationState, PracticeState, CoachingDecision


class ConversationFSM:
    def __init__(self) -> None:
        self._conversation_state = ConversationState.FREE_CHAT
        self._practice_state: PracticeState | None = None

    @property
    def conversation_state(self) -> ConversationState:
        return self._conversation_state

    @property
    def practice_state(self) -> PracticeState | None:
        return self._practice_state

    def transition(self, decision: CoachingDecision) -> bool:
        """Transition conversation state based on coaching decision."""
        cs = self._conversation_state

        if decision == CoachingDecision.EXPLORE:
            if cs in (ConversationState.FREE_CHAT, ConversationState.FOLLOW_UP):
                self._conversation_state = ConversationState.EXPLORE
                return True

        elif decision == CoachingDecision.SUGGEST:
            if cs in (ConversationState.FREE_CHAT, ConversationState.EXPLORE, ConversationState.FOLLOW_UP):
                self._conversation_state = ConversationState.PRACTICE_OFFERED
                return True

        elif decision in (CoachingDecision.LISTEN, CoachingDecision.ANSWER, CoachingDecision.GUIDE):
            # These don't change conversation state
            return True

        return False

    def accept_practice(self) -> bool:
        if self._conversation_state != ConversationState.PRACTICE_OFFERED:
            return False
        self._conversation_state = ConversationState.PRACTICE_ACTIVE
        self._practice_state = PracticeState.CONSENT
        return True

    def decline_practice(self) -> bool:
        if self._conversation_state != ConversationState.PRACTICE_OFFERED:
            return False
        self._conversation_state = ConversationState.FREE_CHAT
        return True

    def pause_practice(self) -> bool:
        if self._conversation_state != ConversationState.PRACTICE_ACTIVE:
            return False
        self._conversation_state = ConversationState.PRACTICE_PAUSED
        return True

    def resume_practice(self) -> bool:
        if self._conversation_state != ConversationState.PRACTICE_PAUSED:
            return False
        self._conversation_state = ConversationState.PRACTICE_ACTIVE
        return True

    def complete_practice(self) -> bool:
        if self._conversation_state != ConversationState.PRACTICE_ACTIVE:
            return False
        self._conversation_state = ConversationState.FOLLOW_UP
        self._practice_state = None
        return True

    def advance_practice_step(self, next_step: str) -> bool:
        if self._conversation_state != ConversationState.PRACTICE_ACTIVE:
            return False
        try:
            self._practice_state = PracticeState(next_step)
            return True
        except ValueError:
            return False

    def enter_crisis(self) -> bool:
        self._conversation_state = ConversationState.CRISIS
        self._practice_state = None
        return True

    def stabilize_from_crisis(self) -> bool:
        if self._conversation_state != ConversationState.CRISIS:
            return False
        self._conversation_state = ConversationState.FREE_CHAT
        return True

    def to_dict(self) -> dict:
        return {
            "conversation_state": self._conversation_state.value,
            "practice_state": self._practice_state.value if self._practice_state else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConversationFSM:
        fsm = cls()
        fsm._conversation_state = ConversationState(data["conversation_state"])
        ps = data.get("practice_state")
        fsm._practice_state = PracticeState(ps) if ps else None
        return fsm
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_coaching_fsm.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/fsm.py packages/telegram-bot/tests/test_coaching_fsm.py
git commit -m "feat(coaching): add 2-level conversation + practice FSM"
```

---

## Task 10: Output Safety Check

Deterministic post-generation check: no diagnoses, no medication, no pressure, correct crisis escalation.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/output_safety.py`
- Test: `packages/telegram-bot/tests/test_output_safety.py`

**Step 1: Write the failing test**

```python
# tests/test_output_safety.py
import pytest
from wellness_bot.coaching.output_safety import OutputSafetyCheck


def test_clean_message_passes():
    check = OutputSafetyCheck()
    result = check.validate("Я понимаю, что тебе сейчас тяжело. Хочешь попробовать технику заземления?")
    assert result.approved is True


def test_diagnosis_blocked():
    check = OutputSafetyCheck()
    result = check.validate("У вас депрессия, вам нужно обратиться к психиатру.")
    assert result.approved is False
    assert "diagnosis" in result.reason


def test_medication_blocked():
    check = OutputSafetyCheck()
    result = check.validate("Попробуйте принять антидепрессанты, они помогут.")
    assert result.approved is False
    assert "medication" in result.reason


def test_pressure_blocked():
    check = OutputSafetyCheck()
    result = check.validate("Ты ОБЯЗАН сделать это упражнение прямо сейчас.")
    assert result.approved is False


def test_english_diagnosis_blocked():
    check = OutputSafetyCheck()
    result = check.validate("You have clinical depression and need medication.")
    assert result.approved is False


def test_safe_wellness_language_passes():
    check = OutputSafetyCheck()
    result = check.validate("Let's try a grounding exercise. Focus on 5 things you can see around you.")
    assert result.approved is True
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_output_safety.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/coaching/output_safety.py
"""Deterministic output safety check. Runs AFTER LLM generation."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SafetyCheckResult:
    approved: bool
    reason: str = ""
    action: str = "pass"  # pass, rewrite, block


_DIAGNOSIS_PATTERNS = [
    re.compile(r"(у\s*вас|у\s*тебя)\s*(депресси[яи]|тревожное\s*расстройство|птср|обсесси|биполярн)", re.I),
    re.compile(r"(ваш|твой)\s*диагноз", re.I),
    re.compile(r"you\s*(have|suffer\s*from)\s*(depression|anxiety\s*disorder|ptsd|ocd|bipolar)", re.I),
    re.compile(r"(clinical|diagnosed\s*with)\s*(depression|anxiety|disorder)", re.I),
]

_MEDICATION_PATTERNS = [
    re.compile(r"(антидепрессант|транквилизатор|нейролептик|снотворн|седативн)", re.I),
    re.compile(r"(принять|принимать|назначить|выпить)\s*(таблетк|лекарств|препарат)", re.I),
    re.compile(r"(antidepressant|tranquilizer|benzodiazepine|ssri|medication|prescri)", re.I),
    re.compile(r"(take|try)\s*(pills|medication|drugs)", re.I),
    re.compile(r"need\s*medication", re.I),
]

_PRESSURE_PATTERNS = [
    re.compile(r"(обязан|должен|немедленно|прямо\s*сейчас)\s*(сделай|выполни|начни)", re.I),
    re.compile(r"you\s*(must|have\s*to|need\s*to)\s*(do\s*this|start|immediately)", re.I),
]


class OutputSafetyCheck:
    def validate(self, text: str) -> SafetyCheckResult:
        for pattern in _DIAGNOSIS_PATTERNS:
            if pattern.search(text):
                return SafetyCheckResult(approved=False, reason="diagnosis", action="rewrite")

        for pattern in _MEDICATION_PATTERNS:
            if pattern.search(text):
                return SafetyCheckResult(approved=False, reason="medication", action="rewrite")

        for pattern in _PRESSURE_PATTERNS:
            if pattern.search(text):
                return SafetyCheckResult(approved=False, reason="pressure", action="rewrite")

        return SafetyCheckResult(approved=True)
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_output_safety.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/output_safety.py packages/telegram-bot/tests/test_output_safety.py
git commit -m "feat(coaching): add deterministic output safety check"
```

---

## Task 11: Coaching Pipeline (wire all components together)

The main pipeline that processes each user message through all 11 steps.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/pipeline.py`
- Test: `packages/telegram-bot/tests/test_coaching_pipeline.py`

**Step 1: Write the failing test**

```python
# tests/test_coaching_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from wellness_bot.coaching.pipeline import CoachingPipeline, PipelineConfig
from wellness_bot.coaching.safety_gate import SafetyGateResult
from wellness_bot.protocol.types import CoachingDecision


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    # Context analyzer response
    provider.chat = AsyncMock(return_value=MagicMock(
        content='{"risk_level":"low","emotional_state":{"anxiety":0.5,"rumination":0.3},'
                '"readiness_for_practice":0.6,"coaching_hypotheses":[],'
                '"confidence":0.8,"candidate_constraints":[]}',
        input_tokens=100,
        output_tokens=50,
    ))
    return provider


@pytest.fixture
def pipeline(mock_provider, tmp_path):
    config = PipelineConfig(db_path=str(tmp_path / "test.db"))
    return CoachingPipeline(llm_provider=mock_provider, config=config)


@pytest.mark.asyncio
async def test_pipeline_processes_safe_message(pipeline, mock_provider):
    # Response generator call
    mock_provider.chat.side_effect = [
        # Context analyzer
        MagicMock(
            content='{"risk_level":"low","emotional_state":{"anxiety":0.3},'
                    '"readiness_for_practice":0.5,"coaching_hypotheses":[],'
                    '"confidence":0.8,"candidate_constraints":[]}',
            input_tokens=100, output_tokens=50,
        ),
        # Response generator
        MagicMock(
            content="Я понимаю. Расскажи подробнее, что тебя беспокоит?",
            input_tokens=100, output_tokens=30,
        ),
    ]
    result = await pipeline.process("user1", "Сегодня тяжёлый день")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_pipeline_crisis_triggers_safety_protocol(pipeline, mock_provider):
    result = await pipeline.process("user1", "хочу покончить с собой")
    assert result is not None
    # Should contain crisis response, not regular coaching
    assert len(result) > 0


@pytest.mark.asyncio
async def test_pipeline_detects_language(pipeline, mock_provider):
    mock_provider.chat.side_effect = [
        MagicMock(content='{"risk_level":"low","emotional_state":{},"readiness_for_practice":0.5,"coaching_hypotheses":[],"confidence":0.8,"candidate_constraints":[]}', input_tokens=100, output_tokens=50),
        MagicMock(content="I understand. Tell me more about how you're feeling.", input_tokens=100, output_tokens=30),
    ]
    result = await pipeline.process("user1", "I'm feeling stressed today")
    assert isinstance(result, str)
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_coaching_pipeline.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/coaching/pipeline.py
"""Main coaching pipeline: wires all 11 components together."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from wellness_bot.coaching.safety_gate import SafetyGate
from wellness_bot.coaching.language_resolver import LanguageResolver
from wellness_bot.coaching.context_analyzer import ContextAnalyzer
from wellness_bot.coaching.opportunity_scorer import OpportunityScorer
from wellness_bot.coaching.practice_selector import PracticeSelector, PracticeCatalogEntry
from wellness_bot.coaching.coach_policy import CoachPolicyEngine
from wellness_bot.coaching.output_safety import OutputSafetyCheck
from wellness_bot.coaching.fsm import ConversationFSM
from wellness_bot.protocol.types import CoachingDecision

logger = logging.getLogger(__name__)

# Crisis response templates by language
_CRISIS_RESPONSES = {
    "ru": (
        "Я слышу тебя. То, что ты чувствуешь — серьёзно, и ты заслуживаешь помощи прямо сейчас.\n\n"
        "Пожалуйста, позвони на линию помощи: 8-800-2000-122 (бесплатно, круглосуточно).\n\n"
        "Я здесь и могу поговорить, но профессиональная помощь сейчас важнее всего."
    ),
    "en": (
        "I hear you. What you're feeling is serious, and you deserve help right now.\n\n"
        "Please call a crisis line: 988 (Suicide & Crisis Lifeline, US) or text HOME to 741741.\n\n"
        "I'm here and can talk, but professional help is the most important thing right now."
    ),
    "es": (
        "Te escucho. Lo que sientes es serio y mereces ayuda ahora mismo.\n\n"
        "Por favor llama a la línea de crisis: 024 (España) o tu línea local de ayuda.\n\n"
        "Estoy aquí y puedo hablar, pero la ayuda profesional es lo más importante ahora."
    ),
}

_DEFAULT_CRISIS = _CRISIS_RESPONSES["en"]


@dataclass
class PipelineConfig:
    db_path: str = "data/wellness.db"
    response_model: str = "claude-sonnet-4-5-20250929"
    context_model: str = "claude-haiku-4-5-20251001"
    max_dialogue_window: int = 10


class CoachingPipeline:
    def __init__(
        self,
        llm_provider,
        config: PipelineConfig | None = None,
        catalog: list[PracticeCatalogEntry] | None = None,
    ) -> None:
        self._config = config or PipelineConfig()
        self._provider = llm_provider

        # Components
        self._safety_gate = SafetyGate()
        self._language_resolver = LanguageResolver()
        self._context_analyzer = ContextAnalyzer(llm_provider, model=self._config.context_model)
        self._opportunity_scorer = OpportunityScorer()
        self._practice_selector = PracticeSelector(catalog or [])
        self._coach_policy = CoachPolicyEngine()
        self._output_safety = OutputSafetyCheck()

        # Per-user state
        self._fsm: dict[str, ConversationFSM] = {}
        self._dialogue: dict[str, list[dict]] = {}
        self._suggestion_history: dict[str, list[dict]] = {}
        self._messages_since_suggest: dict[str, int] = {}

    def _get_fsm(self, user_id: str) -> ConversationFSM:
        if user_id not in self._fsm:
            self._fsm[user_id] = ConversationFSM()
        return self._fsm[user_id]

    async def process(self, user_id: str, text: str) -> str:
        start = time.monotonic()

        # Track dialogue
        if user_id not in self._dialogue:
            self._dialogue[user_id] = []
        self._dialogue[user_id].append({"role": "user", "text": text})
        self._messages_since_suggest[user_id] = self._messages_since_suggest.get(user_id, 0) + 1

        # 1. Safety Gate
        safety_result = self._safety_gate.check(text)
        if safety_result.risk_level == "crisis":
            fsm = self._get_fsm(user_id)
            fsm.enter_crisis()
            language = self._language_resolver.resolve(user_id, text)
            response = _CRISIS_RESPONSES.get(language, _DEFAULT_CRISIS)
            self._dialogue[user_id].append({"role": "assistant", "text": response})
            self._log_decision(user_id, "crisis_protocol", 0.0, None, start)
            return response

        # 2. Language Resolver
        language = self._language_resolver.resolve(user_id, text)

        # 3. Context Analyzer
        window = self._dialogue[user_id][-self._config.max_dialogue_window:]
        context = await self._context_analyzer.analyze(
            user_message=text,
            dialogue_window=window,
            mood_history=[],
            practice_history=[],
            user_profile={},
            language=language,
        )

        # 4. Opportunity Scorer
        opportunity = self._opportunity_scorer.score(
            context=context,
            recent_suggestions=self._suggestion_history.get(user_id, []),
            messages_since_last_suggest=self._messages_since_suggest.get(user_id, 0),
        )

        # 5. Practice Selector
        ranked = []
        if opportunity.allow_proactive_suggest:
            ranked = self._practice_selector.select(
                context=context,
                opportunity_score=opportunity.opportunity_score,
                user_history={},
                top_k=3,
            )

        # 6. Coach Policy Engine
        decision = self._coach_policy.decide(context, opportunity, ranked)

        # Update FSM
        fsm = self._get_fsm(user_id)
        fsm.transition(decision.decision)

        # 7. Response Generator
        response = await self._generate_response(
            user_id=user_id,
            text=text,
            language=language,
            decision=decision,
            context=context,
            window=window,
        )

        # 8. Output Safety Check
        safety_check = self._output_safety.validate(response)
        if not safety_check.approved:
            logger.warning("Output safety blocked: %s", safety_check.reason)
            response = self._safe_fallback(language, decision.decision)

        # Track suggestion if made
        if decision.decision == CoachingDecision.SUGGEST:
            if user_id not in self._suggestion_history:
                self._suggestion_history[user_id] = []
            self._suggestion_history[user_id].append({"accepted": False})
            self._messages_since_suggest[user_id] = 0

        # 11. Audit
        self._log_decision(
            user_id, decision.decision.value,
            opportunity.opportunity_score,
            decision.selected_practice_id, start,
        )

        self._dialogue[user_id].append({"role": "assistant", "text": response})
        return response

    async def _generate_response(
        self, user_id: str, text: str, language: str,
        decision, context, window: list[dict],
    ) -> str:
        style_map = {
            CoachingDecision.LISTEN: "You are a warm, empathetic listener. Reflect what the user said and validate their feelings.",
            CoachingDecision.EXPLORE: "You are a curious, warm coach. Ask one clarifying question to understand the user better.",
            CoachingDecision.SUGGEST: f"You are a proactive wellness coach. Suggest practice '{decision.selected_practice_id}' naturally, explain why it might help based on what the user shared. Ask for consent.",
            CoachingDecision.GUIDE: "You are a gentle coach. Softly direct the conversation toward what might help the user.",
            CoachingDecision.ANSWER: "You are a helpful assistant. Give a direct, concise answer.",
        }

        system = (
            f"{style_map.get(decision.decision, style_map[CoachingDecision.LISTEN])}\n\n"
            f"Respond in {language}. Keep response to 1-3 sentences. "
            f"You are a wellness support coach, NOT a therapist. Never diagnose or prescribe medication."
        )

        messages = []
        for msg in window[-6:]:
            messages.append({"role": msg["role"], "content": msg["text"]})

        try:
            result = await self._provider.chat(
                messages=messages,
                system=system,
                model=self._config.response_model,
            )
            return result.content
        except Exception as e:
            logger.exception("Response generation failed: %s", e)
            return self._safe_fallback(language, decision.decision)

    def _safe_fallback(self, language: str, decision: CoachingDecision) -> str:
        fallbacks = {
            "ru": "Я здесь и слушаю. Расскажи, что тебя беспокоит?",
            "en": "I'm here and listening. Tell me what's on your mind?",
            "es": "Estoy aquí y escucho. Cuéntame qué te preocupa.",
        }
        return fallbacks.get(language, fallbacks["en"])

    def _log_decision(self, user_id, decision, score, practice_id, start):
        latency = int((time.monotonic() - start) * 1000)
        logger.info(
            "decision user=%s decision=%s opportunity=%.2f practice=%s latency=%dms",
            user_id, decision, score, practice_id, latency,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_coaching_pipeline.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/pipeline.py packages/telegram-bot/tests/test_coaching_pipeline.py
git commit -m "feat(coaching): wire all components into coaching pipeline"
```

---

## Task 12: Wire pipeline into Telegram handlers

Replace the old `WellnessBot.process_text()` with the new `CoachingPipeline`. Update `app.py` and `handlers.py`.

**Files:**
- Modify: `packages/telegram-bot/src/wellness_bot/handlers.py`
- Modify: `packages/telegram-bot/src/wellness_bot/app.py`
- Test: `packages/telegram-bot/tests/test_handlers_coaching.py`

**Step 1: Write the failing test**

```python
# tests/test_handlers_coaching.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from wellness_bot.coaching.pipeline import CoachingPipeline, PipelineConfig


@pytest.mark.asyncio
async def test_pipeline_integration_smoke():
    """Smoke test: pipeline can be instantiated and called."""
    provider = AsyncMock()
    provider.chat = AsyncMock(return_value=MagicMock(
        content='{"risk_level":"low","emotional_state":{},"readiness_for_practice":0.5,"coaching_hypotheses":[],"confidence":0.8,"candidate_constraints":[]}',
        input_tokens=100, output_tokens=50,
    ))
    # Second call for response generation
    provider.chat.side_effect = [
        MagicMock(
            content='{"risk_level":"low","emotional_state":{},"readiness_for_practice":0.5,"coaching_hypotheses":[],"confidence":0.8,"candidate_constraints":[]}',
            input_tokens=100, output_tokens=50,
        ),
        MagicMock(content="Привет! Как я могу помочь?", input_tokens=50, output_tokens=20),
    ]
    config = PipelineConfig()
    pipeline = CoachingPipeline(llm_provider=provider, config=config)
    result = await pipeline.process("test_user", "Привет")
    assert isinstance(result, str)
    assert len(result) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_handlers_coaching.py -v`
Expected: should pass (this is a smoke test for existing code)

**Step 3: Update handlers.py**

In `packages/telegram-bot/src/wellness_bot/handlers.py`, replace `process_text` to use `CoachingPipeline`:

- Import `CoachingPipeline` and `PipelineConfig` from `wellness_bot.coaching.pipeline`
- In `WellnessBot.setup()`, create `self.pipeline = CoachingPipeline(llm_provider=self.provider, config=PipelineConfig(db_path=self.config.db_path))`
- In `WellnessBot.process_text()`, call `return await self.pipeline.process(str(user_id), text)`
- Keep the old code path as fallback if pipeline is None

**Step 4: Update app.py**

No changes needed — `app.py` calls `wellness.setup()` which will now init the pipeline.

**Step 5: Run all tests**

Run: `cd packages/telegram-bot && python -m pytest tests/ -v`
Expected: ALL PASS (old tests + new tests)

**Step 6: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/handlers.py packages/telegram-bot/tests/test_handlers_coaching.py
git commit -m "feat(coaching): wire coaching pipeline into Telegram handlers"
```

---

## Task 13: Audit logger and metrics collection

Persist decision logs and metrics to the database.

**Files:**
- Create: `packages/telegram-bot/src/wellness_bot/coaching/audit.py`
- Test: `packages/telegram-bot/tests/test_audit.py`

**Step 1: Write the failing test**

```python
# tests/test_audit.py
import pytest
import aiosqlite
from wellness_bot.coaching.audit import AuditLogger
from wellness_bot.protocol.schema_v2 import apply_coaching_schema


@pytest.fixture
async def db(tmp_path):
    path = str(tmp_path / "test.db")
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        await apply_coaching_schema(conn)
        yield conn


@pytest.mark.asyncio
async def test_log_decision(db):
    logger = AuditLogger(db)
    await logger.log_decision(
        session_id="s1",
        context_state={"risk_level": "low"},
        decision="listen",
        opportunity_score=0.45,
        selected_practice_id=None,
        latency_ms=150,
        cost=0.001,
    )
    cursor = await db.execute("SELECT * FROM decision_logs WHERE session_id='s1'")
    row = await cursor.fetchone()
    assert row is not None
    assert row["decision"] == "listen"
    assert row["latency_ms"] == 150


@pytest.mark.asyncio
async def test_log_safety_event(db):
    logger = AuditLogger(db)
    await logger.log_safety_event(
        session_id="s1",
        detector="keyword_regex",
        severity="crisis",
        action="crisis_protocol",
        message_hash="abc123",
    )
    cursor = await db.execute("SELECT * FROM safety_events WHERE session_id='s1'")
    row = await cursor.fetchone()
    assert row is not None
    assert row["severity"] == "crisis"


@pytest.mark.asyncio
async def test_get_metrics(db):
    logger = AuditLogger(db)
    await logger.log_decision("s1", {}, "suggest", 0.8, "U2", 100, 0.01)
    await logger.log_decision("s2", {}, "listen", 0.3, None, 80, 0.005)
    metrics = await logger.get_metrics()
    assert metrics["total_decisions"] == 2
    assert metrics["suggest_count"] == 1
```

**Step 2: Run test to verify it fails**

Run: `cd packages/telegram-bot && python -m pytest tests/test_audit.py -v`

**Step 3: Write minimal implementation**

```python
# packages/telegram-bot/src/wellness_bot/coaching/audit.py
"""Audit logging and metrics for the coaching pipeline."""
from __future__ import annotations

import json

import aiosqlite


class AuditLogger:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def log_decision(
        self,
        session_id: str,
        context_state: dict,
        decision: str,
        opportunity_score: float,
        selected_practice_id: str | None,
        latency_ms: int,
        cost: float,
    ) -> None:
        await self._db.execute(
            """INSERT INTO decision_logs
               (session_id, context_state_json, decision, opportunity_score,
                selected_practice_id, latency_ms, cost)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, json.dumps(context_state), decision,
             opportunity_score, selected_practice_id, latency_ms, cost),
        )
        await self._db.commit()

    async def log_safety_event(
        self,
        session_id: str,
        detector: str,
        severity: str,
        action: str,
        message_hash: str | None = None,
    ) -> None:
        await self._db.execute(
            """INSERT INTO safety_events
               (session_id, detector, severity, action, message_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, detector, severity, action, message_hash),
        )
        await self._db.commit()

    async def get_metrics(self) -> dict:
        cursor = await self._db.execute("SELECT COUNT(*) FROM decision_logs")
        total = (await cursor.fetchone())[0]

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM decision_logs WHERE decision='suggest'"
        )
        suggest_count = (await cursor.fetchone())[0]

        cursor = await self._db.execute(
            "SELECT AVG(latency_ms) FROM decision_logs"
        )
        avg_latency = (await cursor.fetchone())[0] or 0

        return {
            "total_decisions": total,
            "suggest_count": suggest_count,
            "avg_latency_ms": round(avg_latency, 1),
        }
```

**Step 4: Run test to verify it passes**

Run: `cd packages/telegram-bot && python -m pytest tests/test_audit.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/coaching/audit.py packages/telegram-bot/tests/test_audit.py
git commit -m "feat(coaching): add audit logger and metrics collection"
```

---

## Task 14: Run full test suite and push

**Step 1: Run all coaching tests**

```bash
cd packages/telegram-bot && python -m pytest tests/ -v --tb=short
```

Expected: ALL PASS

**Step 2: Run linter**

```bash
cd packages/agent-core && ruff check src/ tests/
```

**Step 3: Push**

```bash
git push origin main
```
