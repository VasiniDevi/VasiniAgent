"""SQLite-backed session and mood storage."""

from __future__ import annotations

import time

import aiosqlite


class SessionStore:
    """Persistent storage for conversations, moods, and user state."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, created_at);

            CREATE TABLE IF NOT EXISTS moods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                note TEXT DEFAULT '',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_moods_user ON moods(user_id, created_at);

            CREATE TABLE IF NOT EXISTS user_state (
                user_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'onboarding',
                checkin_interval REAL DEFAULT 4.0,
                missed_checkins INTEGER DEFAULT 0,
                quiet_start INTEGER DEFAULT 23,
                quiet_end INTEGER DEFAULT 8,
                updated_at REAL NOT NULL
            );
        """)
        await self._db.commit()

    async def save_message(self, user_id: int, role: str, content: str) -> None:
        await self._db.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, time.time()),
        )
        await self._db.commit()

    async def get_messages(self, user_id: int, limit: int = 20) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT role, content, created_at FROM messages WHERE user_id = ? ORDER BY created_at ASC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]

    async def save_mood(self, user_id: int, score: int, note: str = "") -> None:
        await self._db.execute(
            "INSERT INTO moods (user_id, score, note, created_at) VALUES (?, ?, ?, ?)",
            (user_id, score, note, time.time()),
        )
        await self._db.commit()

    async def get_moods(self, user_id: int, limit: int = 10) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT score, note, created_at FROM moods WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [{"score": r[0], "note": r[1], "created_at": r[2]} for r in rows]

    async def get_user_state(self, user_id: int) -> dict:
        cursor = await self._db.execute(
            "SELECT status, checkin_interval, missed_checkins, quiet_start, quiet_end FROM user_state WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return {"status": "onboarding", "checkin_interval": 4.0, "missed_checkins": 0, "quiet_start": 23, "quiet_end": 8}
        return {"status": row[0], "checkin_interval": row[1], "missed_checkins": row[2], "quiet_start": row[3], "quiet_end": row[4]}

    async def update_user_state(self, user_id: int, **kwargs) -> None:
        existing = await self.get_user_state(user_id)
        merged = {**existing, **kwargs}
        await self._db.execute(
            """INSERT INTO user_state (user_id, status, checkin_interval, missed_checkins, quiet_start, quiet_end, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 status=excluded.status, checkin_interval=excluded.checkin_interval,
                 missed_checkins=excluded.missed_checkins, quiet_start=excluded.quiet_start,
                 quiet_end=excluded.quiet_end, updated_at=excluded.updated_at""",
            (user_id, merged["status"], merged["checkin_interval"], merged["missed_checkins"],
             merged["quiet_start"], merged["quiet_end"], time.time()),
        )
        await self._db.commit()

    async def increment_missed_checkins(self, user_id: int) -> None:
        state = await self.get_user_state(user_id)
        await self.update_user_state(user_id, missed_checkins=state["missed_checkins"] + 1)

    async def reset_missed_checkins(self, user_id: int) -> None:
        await self.update_user_state(user_id, missed_checkins=0)

    async def close(self) -> None:
        if self._db:
            await self._db.close()
