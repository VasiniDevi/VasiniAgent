"""Repository layer with UnitOfWork for protocol engine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Self

import aiosqlite


class SessionRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(self, **kwargs: object) -> None:
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

    async def log_event(self, **kwargs: object) -> None:
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        await self._db.execute(
            f"INSERT INTO safety_events ({cols}) VALUES ({placeholders})",
            tuple(kwargs.values()),
        )

    async def get_recent(self, user_id: int, window_minutes: int) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
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

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        if exc_type is not None:
            await self._db.rollback()
        else:
            await self._db.commit()
