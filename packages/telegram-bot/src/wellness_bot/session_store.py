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

            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tokens_created ON token_usage(created_at);
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

    async def save_token_usage(self, user_id: int, model: str, input_tokens: int, output_tokens: int) -> None:
        await self._db.execute(
            "INSERT INTO token_usage (user_id, model, input_tokens, output_tokens, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, model, input_tokens, output_tokens, time.time()),
        )
        await self._db.commit()

    async def get_token_usage(self, days: int = 30) -> list[dict]:
        since = time.time() - days * 86400
        cursor = await self._db.execute(
            "SELECT user_id, model, input_tokens, output_tokens, created_at FROM token_usage WHERE created_at >= ? ORDER BY created_at DESC",
            (since,),
        )
        rows = await cursor.fetchall()
        return [{"user_id": r[0], "model": r[1], "input_tokens": r[2], "output_tokens": r[3], "created_at": r[4]} for r in rows]

    async def get_token_summary(self) -> dict:
        now = time.time()
        result = {}
        for label, since in [("today", now - 86400), ("week", now - 7 * 86400), ("month", now - 30 * 86400)]:
            cursor = await self._db.execute(
                "SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0) FROM token_usage WHERE created_at >= ?",
                (since,),
            )
            row = await cursor.fetchone()
            result[label] = {"input_tokens": row[0], "output_tokens": row[1]}
        return result

    async def get_all_users(self) -> list[dict]:
        cursor = await self._db.execute("""
            SELECT DISTINCT m.user_id,
                   COALESCE(us.status, 'onboarding') as status,
                   COALESCE(us.missed_checkins, 0) as missed_checkins,
                   MAX(m.created_at) as last_message_at
            FROM messages m
            LEFT JOIN user_state us ON m.user_id = us.user_id
            GROUP BY m.user_id
            ORDER BY last_message_at DESC
        """)
        rows = await cursor.fetchall()
        return [{"user_id": r[0], "status": r[1], "missed_checkins": r[2], "last_message_at": r[3]} for r in rows]

    async def get_recent_messages(self, limit: int = 10) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT user_id, role, content, created_at FROM messages ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [{"user_id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]

    async def close(self) -> None:
        if self._db:
            await self._db.close()
