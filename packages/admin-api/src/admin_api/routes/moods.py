"""Mood history endpoint."""
from __future__ import annotations

import time

import aiosqlite
from fastapi import APIRouter, Depends, Query

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api", tags=["moods"])


@router.get("/moods/{user_id}", dependencies=[Depends(verify_token)])
async def get_moods(
    user_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return mood entries for a user within the given number of days."""
    since = time.time() - days * 86400
    cur = await db.execute(
        "SELECT id, score, note, created_at FROM moods "
        "WHERE user_id = ? AND created_at >= ? ORDER BY created_at DESC",
        (user_id, since),
    )
    rows = await cur.fetchall()
    return {
        "user_id": user_id,
        "days": days,
        "moods": [
            {"id": r[0], "score": r[1], "note": r[2], "created_at": r[3]}
            for r in rows
        ],
    }
