"""Shared dependencies -- database connection and paths."""
from __future__ import annotations

import os
from pathlib import Path

import aiosqlite

DB_PATH = os.getenv("DB_PATH", "../../packages/telegram-bot/data/wellness.db")
PACK_DIR = Path(os.getenv("PACK_DIR", "../../packs/wellness-cbt"))
ENV_PATH = Path(os.getenv("ENV_PATH", "../../packages/telegram-bot/.env"))


async def get_db():
    """Yield an aiosqlite connection, closing it after the request."""
    db = await aiosqlite.connect(DB_PATH)
    try:
        yield db
    finally:
        await db.close()
