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
