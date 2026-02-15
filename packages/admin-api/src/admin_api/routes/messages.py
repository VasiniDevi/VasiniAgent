"""Message history endpoint."""
from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends, Query

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api", tags=["messages"])


@router.get("/messages/{user_id}", dependencies=[Depends(verify_token)])
async def get_messages(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return paginated message history for a user."""
    cur = await db.execute(
        "SELECT id, role, content, created_at FROM messages "
        "WHERE user_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
        (user_id, limit, offset),
    )
    rows = await cur.fetchall()

    # Total count for pagination
    cur = await db.execute(
        "SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,)
    )
    total = (await cur.fetchone())[0]

    return {
        "user_id": user_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "messages": [
            {"id": r[0], "role": r[1], "content": r[2], "created_at": r[3]}
            for r in rows
        ],
    }
