"""Tests for AuditLogger — decision logging and metrics collection."""

import pytest
import aiosqlite

from wellness_bot.protocol.schema_v2 import apply_coaching_schema
from wellness_bot.coaching.audit import AuditLogger


@pytest.fixture
async def db(tmp_path):
    path = str(tmp_path / "test.db")
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        await apply_coaching_schema(conn)
        # Insert prerequisite rows so foreign keys are satisfied.
        await conn.execute(
            "INSERT INTO users (id, telegram_id) VALUES (?, ?)",
            ("u1", 111),
        )
        await conn.execute(
            "INSERT INTO sessions (id, user_id) VALUES (?, ?)",
            ("s1", "u1"),
        )
        await conn.commit()
        yield conn


class TestLogDecision:
    """log_decision inserts correctly and commits."""

    async def test_inserts_single_decision(self, db):
        logger = AuditLogger(db)
        await logger.log_decision(
            session_id="s1",
            context_state={"mood": "neutral", "turn": 3},
            decision="suggest",
            opportunity_score=0.85,
            selected_practice_id="breathing-4-7-8",
            latency_ms=120,
            cost=0.003,
        )

        cursor = await db.execute("SELECT * FROM decision_logs")
        rows = await cursor.fetchall()
        assert len(rows) == 1

        row = rows[0]
        assert row["session_id"] == "s1"
        assert row["context_state_json"] == '{"mood": "neutral", "turn": 3}'
        assert row["decision"] == "suggest"
        assert row["opportunity_score"] == 0.85
        assert row["selected_practice_id"] == "breathing-4-7-8"
        assert row["latency_ms"] == 120
        assert row["cost"] == 0.003

    async def test_inserts_multiple_decisions(self, db):
        logger = AuditLogger(db)
        for i in range(3):
            await logger.log_decision(
                session_id="s1",
                context_state={"turn": i},
                decision="hold" if i < 2 else "suggest",
                opportunity_score=0.1 * i,
                selected_practice_id=None,
                latency_ms=100 + i * 10,
                cost=0.001,
            )

        cursor = await db.execute("SELECT COUNT(*) FROM decision_logs")
        row = await cursor.fetchone()
        assert row[0] == 3

    async def test_context_state_serialized_as_json(self, db):
        logger = AuditLogger(db)
        ctx = {"signals": ["stress"], "mood_score": 0.3}
        await logger.log_decision(
            session_id="s1",
            context_state=ctx,
            decision="hold",
            opportunity_score=0.2,
            selected_practice_id=None,
            latency_ms=50,
            cost=0.0,
        )

        cursor = await db.execute(
            "SELECT context_state_json FROM decision_logs"
        )
        row = await cursor.fetchone()
        import json
        assert json.loads(row["context_state_json"]) == ctx

    async def test_nullable_practice_id(self, db):
        logger = AuditLogger(db)
        await logger.log_decision(
            session_id="s1",
            context_state={},
            decision="hold",
            opportunity_score=0.1,
            selected_practice_id=None,
            latency_ms=30,
            cost=0.0,
        )

        cursor = await db.execute(
            "SELECT selected_practice_id FROM decision_logs"
        )
        row = await cursor.fetchone()
        assert row["selected_practice_id"] is None


class TestLogSafetyEvent:
    """log_safety_event inserts correctly and commits."""

    async def test_inserts_safety_event(self, db):
        logger = AuditLogger(db)
        await logger.log_safety_event(
            session_id="s1",
            detector="keyword_regex",
            severity="crisis",
            action="crisis_protocol",
            message_hash="abc123",
        )

        cursor = await db.execute("SELECT * FROM safety_events")
        rows = await cursor.fetchall()
        assert len(rows) == 1

        row = rows[0]
        assert row["session_id"] == "s1"
        assert row["detector"] == "keyword_regex"
        assert row["severity"] == "crisis"
        assert row["action"] == "crisis_protocol"
        assert row["message_hash"] == "abc123"

    async def test_message_hash_optional(self, db):
        logger = AuditLogger(db)
        await logger.log_safety_event(
            session_id="s1",
            detector="keyword_regex",
            severity="safe",
            action="pass",
        )

        cursor = await db.execute(
            "SELECT message_hash FROM safety_events"
        )
        row = await cursor.fetchone()
        assert row["message_hash"] is None

    async def test_inserts_multiple_events(self, db):
        logger = AuditLogger(db)
        for _ in range(4):
            await logger.log_safety_event(
                session_id="s1",
                detector="keyword_regex",
                severity="safe",
                action="pass",
            )

        cursor = await db.execute("SELECT COUNT(*) FROM safety_events")
        row = await cursor.fetchone()
        assert row[0] == 4


class TestGetMetrics:
    """get_metrics returns correct counts and averages."""

    async def test_metrics_empty_database(self, db):
        logger = AuditLogger(db)
        metrics = await logger.get_metrics()
        assert metrics["total_decisions"] == 0
        assert metrics["suggest_count"] == 0
        assert metrics["avg_latency_ms"] is None

    async def test_metrics_with_decisions(self, db):
        logger = AuditLogger(db)

        # 2 suggests, 1 hold
        await logger.log_decision(
            session_id="s1",
            context_state={},
            decision="suggest",
            opportunity_score=0.8,
            selected_practice_id="p1",
            latency_ms=100,
            cost=0.001,
        )
        await logger.log_decision(
            session_id="s1",
            context_state={},
            decision="suggest",
            opportunity_score=0.9,
            selected_practice_id="p2",
            latency_ms=200,
            cost=0.002,
        )
        await logger.log_decision(
            session_id="s1",
            context_state={},
            decision="hold",
            opportunity_score=0.1,
            selected_practice_id=None,
            latency_ms=300,
            cost=0.001,
        )

        metrics = await logger.get_metrics()
        assert metrics["total_decisions"] == 3
        assert metrics["suggest_count"] == 2
        # avg of 100, 200, 300 = 200.0
        assert metrics["avg_latency_ms"] == 200.0

    async def test_metrics_avg_latency_rounded(self, db):
        logger = AuditLogger(db)

        await logger.log_decision(
            session_id="s1",
            context_state={},
            decision="hold",
            opportunity_score=0.1,
            selected_practice_id=None,
            latency_ms=101,
            cost=0.0,
        )
        await logger.log_decision(
            session_id="s1",
            context_state={},
            decision="hold",
            opportunity_score=0.2,
            selected_practice_id=None,
            latency_ms=102,
            cost=0.0,
        )
        await logger.log_decision(
            session_id="s1",
            context_state={},
            decision="hold",
            opportunity_score=0.3,
            selected_practice_id=None,
            latency_ms=103,
            cost=0.0,
        )

        metrics = await logger.get_metrics()
        # avg of 101, 102, 103 = 102.0
        assert metrics["avg_latency_ms"] == 102.0

    async def test_metrics_returns_dict_keys(self, db):
        logger = AuditLogger(db)
        metrics = await logger.get_metrics()
        assert set(metrics.keys()) == {
            "total_decisions",
            "suggest_count",
            "avg_latency_ms",
        }
