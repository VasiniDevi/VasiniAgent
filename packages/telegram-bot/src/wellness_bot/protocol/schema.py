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
