# tests/test_protocol_repository.py
"""Tests for protocol repository layer."""
import pytest
import aiosqlite
from datetime import datetime, timezone

from wellness_bot.protocol.schema import apply_protocol_schema
from wellness_bot.protocol.repository import SQLiteUnitOfWork


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
