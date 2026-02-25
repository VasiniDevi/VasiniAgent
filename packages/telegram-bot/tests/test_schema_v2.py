# tests/test_schema_v2.py
"""Tests for coaching bot v2 database schema."""
import pytest
import aiosqlite

from wellness_bot.protocol.schema_v2 import apply_coaching_schema


@pytest.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test_v2.db")
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    await conn.close()


EXPECTED_TABLES = {
    "users",
    "user_profiles",
    "sessions",
    "messages",
    "mood_entries",
    "practice_catalog",
    "practice_steps",
    "practice_runs",
    "practice_run_events",
    "practice_outcomes",
    "decision_logs",
    "safety_events",
}

# Table name -> list of required columns
EXPECTED_COLUMNS = {
    "users": ["id", "telegram_id", "created_at"],
    "user_profiles": [
        "user_id", "readiness_score", "preferred_style",
        "language_pref", "patterns_json", "updated_at",
    ],
    "sessions": [
        "id", "user_id", "started_at", "ended_at",
        "language", "conversation_state", "metadata_json",
    ],
    "messages": [
        "id", "session_id", "role", "text",
        "risk_level", "created_at",
    ],
    "mood_entries": [
        "id", "user_id", "session_id",
        "mood_score", "stress_score", "created_at",
    ],
    "practice_catalog": [
        "id", "slug", "title", "targets", "contraindications",
        "duration_min", "duration_max", "protocol_yaml", "active",
    ],
    "practice_steps": [
        "id", "practice_id", "step_order", "step_type", "content",
    ],
    "practice_runs": [
        "id", "user_id", "session_id", "practice_id",
        "state", "current_step", "started_at", "ended_at",
    ],
    "practice_run_events": [
        "id", "run_id", "state_from", "state_to",
        "event", "payload_json", "created_at",
    ],
    "practice_outcomes": [
        "id", "run_id", "baseline_mood", "post_mood",
        "self_report_effect", "completed", "created_at",
    ],
    "decision_logs": [
        "id", "session_id", "context_state_json", "decision",
        "opportunity_score", "selected_practice_id",
        "latency_ms", "cost", "created_at",
    ],
    "safety_events": [
        "id", "session_id", "detector", "severity",
        "action", "message_hash", "created_at",
    ],
}

EXPECTED_INDEXES = {
    "idx_messages_session_created",
    "idx_mood_entries_user_created",
    "idx_practice_outcomes_user_practice",
    "idx_decision_logs_session_created",
    "idx_safety_events_severity_created",
}


class TestSchemaV2Tables:
    """Verify all tables are created."""

    async def test_creates_all_tables(self, db):
        await apply_coaching_schema(db)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        assert EXPECTED_TABLES.issubset(tables), (
            f"Missing tables: {EXPECTED_TABLES - tables}"
        )

    @pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
    async def test_table_exists(self, db, table):
        await apply_coaching_schema(db)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        row = await cursor.fetchone()
        assert row is not None, f"Table '{table}' not found"


class TestSchemaV2Columns:
    """Verify key columns are present in each table."""

    @pytest.mark.parametrize(
        "table,columns",
        sorted(EXPECTED_COLUMNS.items()),
    )
    async def test_key_columns_present(self, db, table, columns):
        await apply_coaching_schema(db)
        cursor = await db.execute(f"PRAGMA table_info({table})")
        actual_cols = {row[1] for row in await cursor.fetchall()}
        missing = set(columns) - actual_cols
        assert not missing, f"Table '{table}' missing columns: {missing}"


class TestSchemaV2Indexes:
    """Verify indexes are created."""

    async def test_all_indexes_created(self, db):
        await apply_coaching_schema(db)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
        missing = EXPECTED_INDEXES - indexes
        assert not missing, f"Missing indexes: {missing}"

    @pytest.mark.parametrize("index_name", sorted(EXPECTED_INDEXES))
    async def test_index_exists(self, db, index_name):
        await apply_coaching_schema(db)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,),
        )
        row = await cursor.fetchone()
        assert row is not None, f"Index '{index_name}' not found"


class TestSchemaV2Idempotent:
    """Verify schema can be applied multiple times without error."""

    async def test_idempotent_apply(self, db):
        await apply_coaching_schema(db)
        await apply_coaching_schema(db)  # second call must not raise

    async def test_idempotent_preserves_data(self, db):
        await apply_coaching_schema(db)
        await db.execute(
            "INSERT INTO users (id, telegram_id) VALUES (?, ?)",
            ("u1", 12345),
        )
        await db.commit()

        # Apply schema again
        await apply_coaching_schema(db)

        cursor = await db.execute("SELECT id FROM users WHERE id = ?", ("u1",))
        row = await cursor.fetchone()
        assert row is not None, "Data lost after idempotent re-apply"


class TestSchemaV2Constraints:
    """Verify key constraints work."""

    async def test_messages_role_check(self, db):
        await apply_coaching_schema(db)
        # Set up required parent rows
        await db.execute(
            "INSERT INTO users (id, telegram_id) VALUES (?, ?)",
            ("u1", 111),
        )
        await db.execute(
            "INSERT INTO sessions (id, user_id) VALUES (?, ?)",
            ("s1", "u1"),
        )
        await db.commit()

        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO messages (session_id, role, text) VALUES (?, ?, ?)",
                ("s1", "INVALID_ROLE", "hello"),
            )
            await db.commit()

    async def test_practice_catalog_slug_unique(self, db):
        await apply_coaching_schema(db)
        await db.execute(
            "INSERT INTO practice_catalog (id, slug, title, duration_min) "
            "VALUES (?, ?, ?, ?)",
            ("p1", "breathing", "Breathing", 3),
        )
        await db.commit()

        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO practice_catalog (id, slug, title, duration_min) "
                "VALUES (?, ?, ?, ?)",
                ("p2", "breathing", "Another Breathing", 5),
            )
            await db.commit()

    async def test_practice_steps_unique_order(self, db):
        await apply_coaching_schema(db)
        await db.execute(
            "INSERT INTO practice_catalog (id, slug, title, duration_min) "
            "VALUES (?, ?, ?, ?)",
            ("p1", "breathing", "Breathing", 3),
        )
        await db.execute(
            "INSERT INTO practice_steps (practice_id, step_order, step_type, content) "
            "VALUES (?, ?, ?, ?)",
            ("p1", 1, "instruction", "Breathe in"),
        )
        await db.commit()

        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO practice_steps (practice_id, step_order, step_type, content) "
                "VALUES (?, ?, ?, ?)",
                ("p1", 1, "instruction", "Duplicate step"),
            )
            await db.commit()

    async def test_users_telegram_id_unique(self, db):
        await apply_coaching_schema(db)
        await db.execute(
            "INSERT INTO users (id, telegram_id) VALUES (?, ?)",
            ("u1", 111),
        )
        await db.commit()

        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO users (id, telegram_id) VALUES (?, ?)",
                ("u2", 111),
            )
            await db.commit()
