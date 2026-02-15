"""GET /api/dashboard -- aggregate stats for the admin dashboard."""
from __future__ import annotations

import time

import aiosqlite
from fastapi import APIRouter, Depends

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", dependencies=[Depends(verify_token)])
async def dashboard(db: aiosqlite.Connection = Depends(get_db)):
    """Return aggregate dashboard statistics."""
    now = time.time()
    day_ago = now - 86400
    week_ago = now - 7 * 86400

    # Total users (distinct user_ids in messages)
    cur = await db.execute(
        "SELECT COUNT(DISTINCT user_id) FROM messages"
    )
    row = await cur.fetchone()
    total_users: int = row[0] if row else 0

    # Active today (distinct user_ids with a message in the last 24h)
    cur = await db.execute(
        "SELECT COUNT(DISTINCT user_id) FROM messages WHERE created_at >= ?",
        (day_ago,),
    )
    row = await cur.fetchone()
    active_today: int = row[0] if row else 0

    # Average mood over the last 7 days
    cur = await db.execute(
        "SELECT AVG(score) FROM moods WHERE created_at >= ?",
        (week_ago,),
    )
    row = await cur.fetchone()
    avg_mood_7d: float | None = round(row[0], 2) if row and row[0] is not None else None

    # Tokens used today
    cur = await db.execute(
        "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) FROM token_usage WHERE created_at >= ?",
        (day_ago,),
    )
    row = await cur.fetchone()
    tokens_today: int = row[0] if row else 0

    # Status counts (how many users in each status)
    cur = await db.execute(
        """SELECT COALESCE(us.status, 'onboarding') AS status, COUNT(DISTINCT m.user_id)
           FROM messages m
           LEFT JOIN user_state us ON m.user_id = us.user_id
           GROUP BY status"""
    )
    rows = await cur.fetchall()
    status_counts: dict[str, int] = {r[0]: r[1] for r in rows}

    # Mood trend -- daily average mood for the last 7 days
    cur = await db.execute(
        """SELECT DATE(created_at, 'unixepoch') AS day, AVG(score)
           FROM moods
           WHERE created_at >= ?
           GROUP BY day
           ORDER BY day""",
        (week_ago,),
    )
    rows = await cur.fetchall()
    mood_trend: list[dict] = [
        {"date": r[0], "avg_score": round(r[1], 2)} for r in rows
    ]

    # Recent messages (last 10)
    cur = await db.execute(
        "SELECT user_id, role, content, created_at FROM messages ORDER BY created_at DESC LIMIT 10"
    )
    rows = await cur.fetchall()
    recent_messages: list[dict] = [
        {"user_id": r[0], "role": r[1], "content": r[2], "created_at": r[3]}
        for r in rows
    ]

    return {
        "total_users": total_users,
        "active_today": active_today,
        "avg_mood_7d": avg_mood_7d,
        "tokens_today": tokens_today,
        "status_counts": status_counts,
        "mood_trend": mood_trend,
        "recent_messages": recent_messages,
    }
