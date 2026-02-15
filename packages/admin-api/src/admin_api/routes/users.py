"""User management endpoints."""
from __future__ import annotations

import time
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api", tags=["users"])


class UserStateUpdate(BaseModel):
    """Fields that may be patched on a user."""
    status: str | None = None
    checkin_interval: float | None = None
    missed_checkins: int | None = None
    quiet_start: int | None = None
    quiet_end: int | None = None


@router.get("/users", dependencies=[Depends(verify_token)])
async def list_users(db: aiosqlite.Connection = Depends(get_db)):
    """List all users with their last mood score."""
    cur = await db.execute("""
        SELECT
            m.user_id,
            COALESCE(us.status, 'onboarding') AS status,
            COALESCE(us.missed_checkins, 0) AS missed_checkins,
            MAX(m.created_at) AS last_message_at,
            (
                SELECT mo.score
                FROM moods mo
                WHERE mo.user_id = m.user_id
                ORDER BY mo.created_at DESC
                LIMIT 1
            ) AS last_mood
        FROM messages m
        LEFT JOIN user_state us ON m.user_id = us.user_id
        GROUP BY m.user_id
        ORDER BY last_message_at DESC
    """)
    rows = await cur.fetchall()
    return [
        {
            "user_id": r[0],
            "status": r[1],
            "missed_checkins": r[2],
            "last_message_at": r[3],
            "last_mood": r[4],
        }
        for r in rows
    ]


@router.get("/users/{user_id}", dependencies=[Depends(verify_token)])
async def get_user(user_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """Get detailed info for a single user."""
    # User state
    cur = await db.execute(
        "SELECT status, checkin_interval, missed_checkins, quiet_start, quiet_end, updated_at "
        "FROM user_state WHERE user_id = ?",
        (user_id,),
    )
    row = await cur.fetchone()
    if row:
        state: dict[str, Any] = {
            "status": row[0],
            "checkin_interval": row[1],
            "missed_checkins": row[2],
            "quiet_start": row[3],
            "quiet_end": row[4],
            "updated_at": row[5],
        }
    else:
        state = {
            "status": "onboarding",
            "checkin_interval": 4.0,
            "missed_checkins": 0,
            "quiet_start": 23,
            "quiet_end": 8,
            "updated_at": None,
        }

    # Message count
    cur = await db.execute(
        "SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,)
    )
    msg_count = (await cur.fetchone())[0]

    # Mood count
    cur = await db.execute(
        "SELECT COUNT(*) FROM moods WHERE user_id = ?", (user_id,)
    )
    mood_count = (await cur.fetchone())[0]

    # Last mood
    cur = await db.execute(
        "SELECT score, note, created_at FROM moods WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    mood_row = await cur.fetchone()
    last_mood = (
        {"score": mood_row[0], "note": mood_row[1], "created_at": mood_row[2]}
        if mood_row
        else None
    )

    return {
        "user_id": user_id,
        **state,
        "message_count": msg_count,
        "mood_count": mood_count,
        "last_mood": last_mood,
    }


@router.patch("/users/{user_id}", dependencies=[Depends(verify_token)])
async def update_user(
    user_id: int,
    body: UserStateUpdate,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Update user state fields (status, checkin_interval, etc.)."""
    # Read current state
    cur = await db.execute(
        "SELECT status, checkin_interval, missed_checkins, quiet_start, quiet_end "
        "FROM user_state WHERE user_id = ?",
        (user_id,),
    )
    row = await cur.fetchone()
    if row:
        current = {
            "status": row[0],
            "checkin_interval": row[1],
            "missed_checkins": row[2],
            "quiet_start": row[3],
            "quiet_end": row[4],
        }
    else:
        current = {
            "status": "onboarding",
            "checkin_interval": 4.0,
            "missed_checkins": 0,
            "quiet_start": 23,
            "quiet_end": 8,
        }

    # Merge only non-None fields from body
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    merged = {**current, **updates}

    await db.execute(
        """INSERT INTO user_state (user_id, status, checkin_interval, missed_checkins, quiet_start, quiet_end, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
             status=excluded.status,
             checkin_interval=excluded.checkin_interval,
             missed_checkins=excluded.missed_checkins,
             quiet_start=excluded.quiet_start,
             quiet_end=excluded.quiet_end,
             updated_at=excluded.updated_at""",
        (
            user_id,
            merged["status"],
            merged["checkin_interval"],
            merged["missed_checkins"],
            merged["quiet_start"],
            merged["quiet_end"],
            time.time(),
        ),
    )
    await db.commit()
    return {"ok": True, "user_id": user_id, **merged}


@router.post("/users/{user_id}/reset-checkins", dependencies=[Depends(verify_token)])
async def reset_checkins(
    user_id: int, db: aiosqlite.Connection = Depends(get_db)
):
    """Reset the missed-checkins counter for a user."""
    await db.execute(
        """INSERT INTO user_state (user_id, status, checkin_interval, missed_checkins, quiet_start, quiet_end, updated_at)
           VALUES (?, 'onboarding', 4.0, 0, 23, 8, ?)
           ON CONFLICT(user_id) DO UPDATE SET missed_checkins=0, updated_at=excluded.updated_at""",
        (user_id, time.time()),
    )
    await db.commit()
    return {"ok": True, "user_id": user_id, "missed_checkins": 0}
