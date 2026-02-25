"""V2 database schema for the coaching bot pipeline.

This schema supports the full coaching lifecycle: users, sessions,
messages, mood tracking, practice catalog/runs/outcomes, decision
logging, and safety events.

Separate from the v1 protocol engine schema in schema.py.
"""
from __future__ import annotations

import aiosqlite

COACHING_SCHEMA = """
-- ───────── users ─────────
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ───────── user_profiles ─────────
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id         TEXT PRIMARY KEY REFERENCES users(id),
    readiness_score REAL DEFAULT 0.5,
    preferred_style TEXT DEFAULT 'warm_supportive',
    language_pref   TEXT,
    patterns_json   TEXT DEFAULT '[]',
    updated_at      TEXT
);

-- ───────── sessions ─────────
CREATE TABLE IF NOT EXISTS sessions (
    id                 TEXT PRIMARY KEY,
    user_id            TEXT NOT NULL REFERENCES users(id),
    started_at         TEXT,
    ended_at           TEXT,
    language           TEXT NOT NULL DEFAULT 'ru',
    conversation_state TEXT NOT NULL DEFAULT 'free_chat',
    metadata_json      TEXT DEFAULT '{}'
);

-- ───────── messages ─────────
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text       TEXT NOT NULL,
    risk_level TEXT DEFAULT 'low',
    created_at TEXT
);

-- ───────── mood_entries ─────────
CREATE TABLE IF NOT EXISTS mood_entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT NOT NULL REFERENCES users(id),
    session_id   TEXT REFERENCES sessions(id),
    mood_score   REAL NOT NULL,
    stress_score REAL,
    created_at   TEXT
);

-- ───────── practice_catalog ─────────
CREATE TABLE IF NOT EXISTS practice_catalog (
    id                TEXT PRIMARY KEY,
    slug              TEXT UNIQUE NOT NULL,
    title             TEXT NOT NULL,
    targets           TEXT NOT NULL DEFAULT '[]',
    contraindications TEXT NOT NULL DEFAULT '[]',
    duration_min      INTEGER NOT NULL,
    duration_max      INTEGER,
    protocol_yaml     TEXT,
    active            INTEGER NOT NULL DEFAULT 1
);

-- ───────── practice_steps ─────────
CREATE TABLE IF NOT EXISTS practice_steps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    practice_id TEXT NOT NULL REFERENCES practice_catalog(id),
    step_order  INTEGER NOT NULL,
    step_type   TEXT NOT NULL,
    content     TEXT NOT NULL,
    UNIQUE(practice_id, step_order)
);

-- ───────── practice_runs ─────────
CREATE TABLE IF NOT EXISTS practice_runs (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id),
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    practice_id  TEXT NOT NULL REFERENCES practice_catalog(id),
    state        TEXT NOT NULL DEFAULT 'consent',
    current_step INTEGER NOT NULL DEFAULT 0,
    started_at   TEXT,
    ended_at     TEXT
);

-- ───────── practice_run_events ─────────
CREATE TABLE IF NOT EXISTS practice_run_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES practice_runs(id),
    state_from   TEXT NOT NULL,
    state_to     TEXT NOT NULL,
    event        TEXT NOT NULL,
    payload_json TEXT DEFAULT '{}',
    created_at   TEXT
);

-- ───────── practice_outcomes ─────────
CREATE TABLE IF NOT EXISTS practice_outcomes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id             TEXT NOT NULL REFERENCES practice_runs(id),
    baseline_mood      REAL,
    post_mood          REAL,
    self_report_effect REAL,
    completed          INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT
);

-- ───────── decision_logs ─────────
CREATE TABLE IF NOT EXISTS decision_logs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           TEXT NOT NULL REFERENCES sessions(id),
    context_state_json   TEXT NOT NULL,
    decision             TEXT NOT NULL,
    opportunity_score    REAL,
    selected_practice_id TEXT,
    latency_ms           INTEGER,
    cost                 REAL,
    created_at           TEXT
);

-- ───────── safety_events ─────────
CREATE TABLE IF NOT EXISTS safety_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT REFERENCES sessions(id),
    detector     TEXT NOT NULL,
    severity     TEXT NOT NULL,
    action       TEXT NOT NULL,
    message_hash TEXT,
    created_at   TEXT
);

-- ───────── indexes ─────────
CREATE INDEX IF NOT EXISTS idx_messages_session_created
    ON messages(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mood_entries_user_created
    ON mood_entries(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_practice_outcomes_user_practice
    ON practice_outcomes(run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_decision_logs_session_created
    ON decision_logs(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_safety_events_severity_created
    ON safety_events(severity, created_at DESC);
"""


async def apply_coaching_schema(db: aiosqlite.Connection) -> None:
    """Apply coaching bot v2 schema. Idempotent (IF NOT EXISTS)."""
    await db.executescript(COACHING_SCHEMA)
