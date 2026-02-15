# Admin Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full admin panel (FastAPI + React SPA) for the Wellness CBT Telegram Agent — user monitoring, agent pack editing, token tracking, and bot settings.

**Architecture:** FastAPI backend shares SQLite with the running bot, serves REST API on :8080. React SPA (Vite + Tailwind + shadcn/ui + Recharts) on :5173 proxied to backend. Single bearer token auth.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, aiosqlite, Vite, React 18, TypeScript, Tailwind CSS, shadcn/ui, Recharts, react-router-dom

---

## Phase 1: Backend — Token Tracking + Admin API

### Task 1: Add token_usage table to SessionStore

**Files:**
- Modify: `packages/telegram-bot/src/wellness_bot/session_store.py`
- Modify: `packages/telegram-bot/src/wellness_bot/handlers.py`
- Modify: `packages/telegram-bot/tests/test_session_store.py`

**Step 1: Add token tracking methods to SessionStore**

Add to the `init()` method's SQL, after the `user_state` table creation:

```python
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tokens_created ON token_usage(created_at);
```

Add these methods to `SessionStore`:

```python
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

    async def get_dashboard_stats(self) -> dict:
        now = time.time()
        today = now - 86400
        week = now - 7 * 86400

        # Total users
        cursor = await self._db.execute("SELECT COUNT(DISTINCT user_id) FROM messages")
        total_users = (await cursor.fetchone())[0]

        # Active today
        cursor = await self._db.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE created_at >= ?", (today,))
        active_today = (await cursor.fetchone())[0]

        # Avg mood 7d
        cursor = await self._db.execute("SELECT AVG(score) FROM moods WHERE created_at >= ?", (week,))
        row = await cursor.fetchone()
        avg_mood = round(row[0], 1) if row[0] else 0

        # Status counts
        cursor = await self._db.execute("SELECT status, COUNT(*) FROM user_state GROUP BY status")
        status_counts = {r[0]: r[1] for r in await cursor.fetchall()}

        # Token summary
        token_summary = await self.get_token_summary()

        return {
            "total_users": total_users,
            "active_today": active_today,
            "avg_mood_7d": avg_mood,
            "status_counts": status_counts,
            "tokens": token_summary,
        }

    async def get_mood_trend(self, days: int = 30) -> list[dict]:
        since = time.time() - days * 86400
        cursor = await self._db.execute(
            "SELECT user_id, score, note, created_at FROM moods WHERE created_at >= ? ORDER BY created_at ASC",
            (since,),
        )
        rows = await cursor.fetchall()
        return [{"user_id": r[0], "score": r[1], "note": r[2], "created_at": r[3]} for r in rows]

    async def get_recent_messages(self, limit: int = 10) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT user_id, role, content, created_at FROM messages ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [{"user_id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]
```

**Step 2: Wire token tracking into handlers.py**

In `process_text()` method of `WellnessBot`, after the line `reply = response.content`, add:

```python
        # Track token usage
        usage = response.usage
        if usage:
            await self.store.save_token_usage(
                user_id=user_id,
                model=response.model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )
```

**Step 3: Add tests**

Add to `test_session_store.py`:

```python
    async def test_save_and_get_token_usage(self, store):
        await store.save_token_usage(user_id=123, model="claude-sonnet", input_tokens=100, output_tokens=50)
        usage = await store.get_token_usage(days=1)
        assert len(usage) == 1
        assert usage[0]["input_tokens"] == 100
        assert usage[0]["output_tokens"] == 50

    async def test_token_summary(self, store):
        await store.save_token_usage(user_id=123, model="claude-sonnet", input_tokens=100, output_tokens=50)
        summary = await store.get_token_summary()
        assert summary["today"]["input_tokens"] == 100
        assert summary["today"]["output_tokens"] == 50

    async def test_get_all_users(self, store):
        await store.save_message(user_id=111, role="user", content="Hello")
        await store.save_message(user_id=222, role="user", content="Hi")
        users = await store.get_all_users()
        assert len(users) == 2

    async def test_dashboard_stats(self, store):
        await store.save_message(user_id=111, role="user", content="Hello")
        await store.save_mood(user_id=111, score=7)
        stats = await store.get_dashboard_stats()
        assert stats["total_users"] == 1
        assert stats["active_today"] == 1

    async def test_get_recent_messages(self, store):
        await store.save_message(user_id=111, role="user", content="Msg 1")
        await store.save_message(user_id=111, role="assistant", content="Reply 1")
        recent = await store.get_recent_messages(limit=5)
        assert len(recent) == 2
```

**Step 4: Run tests**

```bash
cd packages/telegram-bot
python3 -m pytest tests/test_session_store.py -v
```

Expected: All tests PASS (8 old + 5 new = 13)

**Step 5: Commit**

```bash
git add packages/telegram-bot/src/wellness_bot/session_store.py \
  packages/telegram-bot/src/wellness_bot/handlers.py \
  packages/telegram-bot/tests/test_session_store.py
git commit -m "feat: add token tracking and dashboard queries to SessionStore"
```

---

### Task 2: Create admin-api package with FastAPI + auth

**Files:**
- Create: `packages/admin-api/pyproject.toml`
- Create: `packages/admin-api/src/admin_api/__init__.py`
- Create: `packages/admin-api/src/admin_api/auth.py`
- Create: `packages/admin-api/src/admin_api/deps.py`
- Create: `packages/admin-api/src/admin_api/app.py`
- Create: `packages/admin-api/tests/__init__.py`
- Create: `packages/admin-api/tests/test_auth.py`

**Step 1: Write pyproject.toml**

```toml
[project]
name = "wellness-admin-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "aiosqlite>=0.20",
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.hatch.build.targets.wheel]
packages = ["src/admin_api"]
```

**Step 2: Write auth.py**

```python
"""Bearer token authentication."""

from __future__ import annotations

import os

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-token-change-me")


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials
```

**Step 3: Write deps.py**

```python
"""Shared dependencies — database connection and paths."""

from __future__ import annotations

import os
from pathlib import Path

import aiosqlite


DB_PATH = os.getenv("DB_PATH", "../../packages/telegram-bot/data/wellness.db")
PACK_DIR = Path(os.getenv("PACK_DIR", "../../packs/wellness-cbt"))
ENV_PATH = Path(os.getenv("ENV_PATH", "../../packages/telegram-bot/.env"))


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    try:
        yield db
    finally:
        await db.close()
```

**Step 4: Write app.py**

```python
"""FastAPI admin API application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Wellness Admin API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

**Step 5: Write __init__.py**

```python
"""Wellness Admin API."""
```

**Step 6: Write test_auth.py**

```python
"""Tests for auth middleware."""

import pytest
from fastapi.testclient import TestClient

from admin_api.app import app
from admin_api.auth import verify_token, ADMIN_TOKEN


class TestAuth:

    def test_health_no_auth(self):
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
```

**Step 7: Install and run tests**

```bash
cd packages/admin-api
pip3 install -e ".[dev]"
python3 -m pytest tests/ -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add packages/admin-api/
git commit -m "feat: create admin-api package with FastAPI and auth"
```

---

### Task 3: Dashboard API endpoint

**Files:**
- Create: `packages/admin-api/src/admin_api/routes/__init__.py`
- Create: `packages/admin-api/src/admin_api/routes/dashboard.py`
- Create: `packages/admin-api/tests/test_dashboard.py`
- Modify: `packages/admin-api/src/admin_api/app.py` (include router)

**Step 1: Write dashboard.py**

```python
"""Dashboard API — overview stats."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

import aiosqlite

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(
    db: aiosqlite.Connection = Depends(get_db),
    _: str = Depends(verify_token),
):
    now = time.time()
    today = now - 86400
    week = now - 7 * 86400

    # Total users
    cursor = await db.execute("SELECT COUNT(DISTINCT user_id) FROM messages")
    total_users = (await cursor.fetchone())[0]

    # Active today
    cursor = await db.execute(
        "SELECT COUNT(DISTINCT user_id) FROM messages WHERE created_at >= ?", (today,)
    )
    active_today = (await cursor.fetchone())[0]

    # Avg mood 7d
    cursor = await db.execute(
        "SELECT AVG(score) FROM moods WHERE created_at >= ?", (week,)
    )
    row = await cursor.fetchone()
    avg_mood = round(row[0], 1) if row[0] else 0

    # Status counts
    cursor = await db.execute("SELECT status, COUNT(*) FROM user_state GROUP BY status")
    status_counts = {r[0]: r[1] for r in await cursor.fetchall()}

    # Token totals
    cursor = await db.execute(
        "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM token_usage WHERE created_at >= ?",
        (today,),
    )
    tok = await cursor.fetchone()
    tokens_today = {"input": tok[0], "output": tok[1]}

    # Mood trend (30d)
    cursor = await db.execute(
        "SELECT score, created_at FROM moods WHERE created_at >= ? ORDER BY created_at",
        (now - 30 * 86400,),
    )
    mood_trend = [{"score": r[0], "created_at": r[1]} for r in await cursor.fetchall()]

    # Recent messages
    cursor = await db.execute(
        "SELECT user_id, role, content, created_at FROM messages ORDER BY created_at DESC LIMIT 10"
    )
    recent = [{"user_id": r[0], "role": r[1], "content": r[2], "created_at": r[3]}
              for r in await cursor.fetchall()]

    return {
        "total_users": total_users,
        "active_today": active_today,
        "avg_mood_7d": avg_mood,
        "tokens_today": tokens_today,
        "status_counts": status_counts,
        "mood_trend": mood_trend,
        "recent_messages": recent,
    }
```

**Step 2: Include router in app.py**

Add to `app.py` after the middleware:

```python
from admin_api.routes.dashboard import router as dashboard_router
app.include_router(dashboard_router)
```

**Step 3: Write test**

```python
"""Tests for dashboard endpoint."""

import time
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from admin_api.app import app
from admin_api.auth import ADMIN_TOKEN


class TestDashboard:

    def test_dashboard_requires_auth(self):
        client = TestClient(app)
        resp = client.get("/api/dashboard")
        assert resp.status_code == 403

    def test_dashboard_rejects_bad_token(self):
        client = TestClient(app)
        resp = client.get("/api/dashboard", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401
```

**Step 4: Run tests**

```bash
cd packages/admin-api
python3 -m pytest tests/ -v
```

**Step 5: Commit**

```bash
git add packages/admin-api/
git commit -m "feat: add dashboard API endpoint"
```

---

### Task 4: Users, Messages, Moods API endpoints

**Files:**
- Create: `packages/admin-api/src/admin_api/routes/users.py`
- Create: `packages/admin-api/src/admin_api/routes/messages.py`
- Create: `packages/admin-api/src/admin_api/routes/moods.py`
- Modify: `packages/admin-api/src/admin_api/app.py` (include routers)

**Step 1: Write users.py**

```python
"""Users API — list, detail, update."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

import aiosqlite

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
async def list_users(
    db: aiosqlite.Connection = Depends(get_db),
    _: str = Depends(verify_token),
):
    cursor = await db.execute("""
        SELECT DISTINCT m.user_id,
               COALESCE(us.status, 'onboarding') as status,
               COALESCE(us.missed_checkins, 0) as missed_checkins,
               COALESCE(us.checkin_interval, 4.0) as checkin_interval,
               MAX(m.created_at) as last_message_at
        FROM messages m
        LEFT JOIN user_state us ON m.user_id = us.user_id
        GROUP BY m.user_id
        ORDER BY last_message_at DESC
    """)
    rows = await cursor.fetchall()

    users = []
    for r in rows:
        # Get latest mood
        mc = await db.execute(
            "SELECT score FROM moods WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (r[0],),
        )
        mood_row = await mc.fetchone()
        users.append({
            "user_id": r[0],
            "status": r[1],
            "missed_checkins": r[2],
            "checkin_interval": r[3],
            "last_message_at": r[4],
            "last_mood": mood_row[0] if mood_row else None,
        })
    return users


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: str = Depends(verify_token),
):
    cursor = await db.execute(
        "SELECT status, checkin_interval, missed_checkins, quiet_start, quiet_end FROM user_state WHERE user_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    if row:
        return {"user_id": user_id, "status": row[0], "checkin_interval": row[1],
                "missed_checkins": row[2], "quiet_start": row[3], "quiet_end": row[4]}
    return {"user_id": user_id, "status": "onboarding", "checkin_interval": 4.0,
            "missed_checkins": 0, "quiet_start": 23, "quiet_end": 8}


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    updates: dict,
    db: aiosqlite.Connection = Depends(get_db),
    _: str = Depends(verify_token),
):
    allowed = {"status", "checkin_interval", "missed_checkins", "quiet_start", "quiet_end"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return {"ok": False, "error": "No valid fields"}

    # Upsert
    existing = await get_user(user_id, db, _)
    merged = {**existing, **filtered}
    await db.execute(
        """INSERT INTO user_state (user_id, status, checkin_interval, missed_checkins, quiet_start, quiet_end, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
             status=excluded.status, checkin_interval=excluded.checkin_interval,
             missed_checkins=excluded.missed_checkins, quiet_start=excluded.quiet_start,
             quiet_end=excluded.quiet_end, updated_at=excluded.updated_at""",
        (user_id, merged["status"], merged["checkin_interval"], merged["missed_checkins"],
         merged["quiet_start"], merged["quiet_end"], time.time()),
    )
    await db.commit()
    return {"ok": True}


@router.post("/{user_id}/reset-checkins")
async def reset_checkins(
    user_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: str = Depends(verify_token),
):
    await db.execute(
        "UPDATE user_state SET missed_checkins = 0, updated_at = ? WHERE user_id = ?",
        (time.time(), user_id),
    )
    await db.commit()
    return {"ok": True}
```

**Step 2: Write messages.py**

```python
"""Messages API — conversation history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

import aiosqlite

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get("/{user_id}")
async def get_messages(
    user_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
    _: str = Depends(verify_token),
):
    cursor = await db.execute(
        "SELECT role, content, created_at FROM messages WHERE user_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
        (user_id, limit, offset),
    )
    rows = await cursor.fetchall()
    return [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]
```

**Step 3: Write moods.py**

```python
"""Moods API — mood data and trends."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query

import aiosqlite

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api/moods", tags=["moods"])


@router.get("/{user_id}")
async def get_moods(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    db: aiosqlite.Connection = Depends(get_db),
    _: str = Depends(verify_token),
):
    since = time.time() - days * 86400
    cursor = await db.execute(
        "SELECT score, note, created_at FROM moods WHERE user_id = ? AND created_at >= ? ORDER BY created_at ASC",
        (user_id, since),
    )
    rows = await cursor.fetchall()
    return [{"score": r[0], "note": r[1], "created_at": r[2]} for r in rows]
```

**Step 4: Include routers in app.py**

```python
from admin_api.routes.dashboard import router as dashboard_router
from admin_api.routes.users import router as users_router
from admin_api.routes.messages import router as messages_router
from admin_api.routes.moods import router as moods_router

app.include_router(dashboard_router)
app.include_router(users_router)
app.include_router(messages_router)
app.include_router(moods_router)
```

**Step 5: Commit**

```bash
git add packages/admin-api/
git commit -m "feat: add users, messages, moods API endpoints"
```

---

### Task 5: Agent pack + monitoring + config API endpoints

**Files:**
- Create: `packages/admin-api/src/admin_api/routes/agent.py`
- Create: `packages/admin-api/src/admin_api/routes/monitoring.py`
- Create: `packages/admin-api/src/admin_api/routes/config.py`
- Modify: `packages/admin-api/src/admin_api/app.py` (include routers)

**Step 1: Write agent.py**

```python
"""Agent pack API — read/write YAML layers, prompt preview."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from admin_api.auth import verify_token
from admin_api.deps import PACK_DIR

# Add agent-core to path for Composer
AGENT_CORE = Path(__file__).resolve().parents[4] / "agent-core" / "src"
if str(AGENT_CORE) not in sys.path:
    sys.path.insert(0, str(AGENT_CORE))

router = APIRouter(prefix="/api/agent", tags=["agent"])

VALID_LAYERS = {"soul", "role", "tools", "guardrails", "memory", "workflow"}


@router.get("/pack")
async def get_all_layers(_: str = Depends(verify_token)):
    layers = {}
    for layer in VALID_LAYERS:
        path = PACK_DIR / f"{layer}.yaml"
        if path.exists():
            layers[layer] = path.read_text(encoding="utf-8")
    return {"layers": layers}


@router.get("/pack/{layer}")
async def get_layer(layer: str, _: str = Depends(verify_token)):
    if layer not in VALID_LAYERS:
        raise HTTPException(400, f"Invalid layer: {layer}")
    path = PACK_DIR / f"{layer}.yaml"
    if not path.exists():
        raise HTTPException(404, f"Layer file not found: {layer}")
    return {"layer": layer, "content": path.read_text(encoding="utf-8")}


class LayerUpdate(BaseModel):
    content: str


@router.put("/pack/{layer}")
async def update_layer(layer: str, body: LayerUpdate, _: str = Depends(verify_token)):
    if layer not in VALID_LAYERS:
        raise HTTPException(400, f"Invalid layer: {layer}")
    path = PACK_DIR / f"{layer}.yaml"

    # Validate by attempting to load the entire pack with new content
    import tempfile, shutil, yaml
    try:
        yaml.safe_load(body.content)  # Basic YAML parse check
    except yaml.YAMLError as e:
        raise HTTPException(422, f"Invalid YAML: {e}")

    # Write and validate via Composer
    backup = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text(body.content, encoding="utf-8")

    try:
        from vasini.composer import Composer
        Composer().load(PACK_DIR)
    except Exception as e:
        # Rollback
        if backup is not None:
            path.write_text(backup, encoding="utf-8")
        raise HTTPException(422, f"Pack validation failed: {e}")

    return {"ok": True, "layer": layer}


@router.get("/prompt-preview")
async def prompt_preview(_: str = Depends(verify_token)):
    try:
        from vasini.composer import Composer
        from vasini.runtime.agent import AgentRuntime
        from vasini.llm.router import LLMRouter, LLMRouterConfig, ModelTier

        config = Composer().load(PACK_DIR)
        llm_config = LLMRouterConfig(
            tier_mapping={ModelTier.TIER_2: "claude-sonnet-4-5-20250929"},
            default_tier=ModelTier.TIER_2,
            fallback_chain=[ModelTier.TIER_2],
        )
        runtime = AgentRuntime(config=config, llm_router=LLMRouter(config=llm_config))
        prompt = runtime._build_system_prompt()
        return {"prompt": prompt}
    except Exception as e:
        raise HTTPException(500, f"Failed to build prompt: {e}")
```

**Step 2: Write monitoring.py**

```python
"""Monitoring API — token usage and costs."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query

import aiosqlite

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# Approximate costs per 1M tokens (USD)
MODEL_COSTS = {
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
}


@router.get("/tokens")
async def get_tokens(
    days: int = Query(30, ge=1, le=365),
    db: aiosqlite.Connection = Depends(get_db),
    _: str = Depends(verify_token),
):
    since = time.time() - days * 86400
    cursor = await db.execute(
        "SELECT user_id, model, input_tokens, output_tokens, created_at FROM token_usage WHERE created_at >= ? ORDER BY created_at DESC",
        (since,),
    )
    rows = await cursor.fetchall()
    result = []
    for r in rows:
        model = r[1]
        costs = MODEL_COSTS.get(model, {"input": 3.0, "output": 15.0})
        cost = (r[2] * costs["input"] + r[3] * costs["output"]) / 1_000_000
        result.append({
            "user_id": r[0], "model": model,
            "input_tokens": r[2], "output_tokens": r[3],
            "cost": round(cost, 4), "created_at": r[4],
        })
    return result


@router.get("/summary")
async def get_summary(
    db: aiosqlite.Connection = Depends(get_db),
    _: str = Depends(verify_token),
):
    now = time.time()
    result = {}
    for label, since in [("today", now - 86400), ("week", now - 7 * 86400), ("month", now - 30 * 86400)]:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM token_usage WHERE created_at >= ?",
            (since,),
        )
        row = await cursor.fetchone()
        cost = (row[0] * 3.0 + row[1] * 15.0) / 1_000_000  # Default sonnet pricing
        result[label] = {"input_tokens": row[0], "output_tokens": row[1], "cost": round(cost, 4)}
    return result
```

**Step 3: Write config.py**

```python
"""Config API — bot settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from admin_api.auth import verify_token
from admin_api.deps import ENV_PATH

router = APIRouter(prefix="/api/config", tags=["config"])

SAFE_KEYS = {
    "CLAUDE_MODEL", "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL",
    "CHECKIN_INTERVAL_HOURS", "QUIET_HOURS_START", "QUIET_HOURS_END",
    "PACK_DIR", "DB_PATH", "ALLOWED_USER_IDS",
}

SECRET_KEYS = {"TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY"}


def _read_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    result = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"')
    return result


def _write_env(data: dict[str, str]) -> None:
    lines = []
    for key, value in data.items():
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


@router.get("")
async def get_config(_: str = Depends(verify_token)):
    env = _read_env()
    safe = {k: v for k, v in env.items() if k in SAFE_KEYS}
    secrets = {k: "***" for k in SECRET_KEYS if k in env}
    return {**safe, **secrets}


@router.patch("")
async def update_config(updates: dict, _: str = Depends(verify_token)):
    forbidden = SECRET_KEYS & set(updates.keys())
    if forbidden:
        raise HTTPException(400, f"Cannot update secret keys via API: {forbidden}")
    invalid = set(updates.keys()) - SAFE_KEYS
    if invalid:
        raise HTTPException(400, f"Unknown config keys: {invalid}")

    env = _read_env()
    env.update(updates)
    _write_env(env)
    return {"ok": True}
```

**Step 4: Include all routers in app.py**

Final `app.py`:

```python
"""FastAPI admin API application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from admin_api.routes.dashboard import router as dashboard_router
from admin_api.routes.users import router as users_router
from admin_api.routes.messages import router as messages_router
from admin_api.routes.moods import router as moods_router
from admin_api.routes.agent import router as agent_router
from admin_api.routes.monitoring import router as monitoring_router
from admin_api.routes.config import router as config_router

app = FastAPI(title="Wellness Admin API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(users_router)
app.include_router(messages_router)
app.include_router(moods_router)
app.include_router(agent_router)
app.include_router(monitoring_router)
app.include_router(config_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

**Step 5: Commit**

```bash
git add packages/admin-api/
git commit -m "feat: add agent pack, monitoring, config API endpoints"
```

---

## Phase 2: Frontend — React SPA

### Task 6: Create admin-ui package (Vite + React + Tailwind + shadcn/ui)

**Step 1: Scaffold Vite project**

```bash
cd packages
npm create vite@latest admin-ui -- --template react-ts
cd admin-ui
npm install
```

**Step 2: Install dependencies**

```bash
npm install react-router-dom recharts tailwindcss @tailwindcss/vite
npm install -D @types/react-router-dom
```

**Step 3: Configure Tailwind**

Update `vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
    },
  },
})
```

Replace `src/index.css` with:

```css
@import "tailwindcss";
```

**Step 4: Write api.ts**

```typescript
const TOKEN = localStorage.getItem('admin_token') || 'dev-token-change-me';

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...options,
    headers: {
      'Authorization': `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export default api;
```

**Step 5: Write Layout.tsx**

```tsx
import { Link, Outlet, useLocation } from 'react-router-dom';

const NAV = [
  { path: '/', label: 'Dashboard', icon: '📊' },
  { path: '/users', label: 'Users', icon: '👥' },
  { path: '/agent', label: 'Agent', icon: '🧠' },
  { path: '/monitoring', label: 'Monitoring', icon: '📈' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
];

export default function Layout() {
  const location = useLocation();

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-56 bg-white border-r border-gray-200 p-4">
        <h1 className="text-lg font-bold mb-6 text-gray-800">Wellness Admin</h1>
        <nav className="space-y-1">
          {NAV.map(({ path, label, icon }) => (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
                location.pathname === path
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <span>{icon}</span>
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
```

**Step 6: Write App.tsx**

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Users from './pages/Users';
import UserDetail from './pages/UserDetail';
import AgentEditor from './pages/AgentEditor';
import Monitoring from './pages/Monitoring';
import Settings from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/users" element={<Users />} />
          <Route path="/users/:id" element={<UserDetail />} />
          <Route path="/agent" element={<AgentEditor />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

**Step 7: Update main.tsx**

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

**Step 8: Commit**

```bash
git add packages/admin-ui/
git commit -m "feat: scaffold admin-ui with Vite + React + Tailwind + routing"
```

---

### Task 7: Dashboard page

**Files:**
- Create: `packages/admin-ui/src/pages/Dashboard.tsx`
- Create: `packages/admin-ui/src/components/StatsCard.tsx`
- Create: `packages/admin-ui/src/components/MoodChart.tsx`

**Step 1: Write StatsCard.tsx**

```tsx
interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
}

export default function StatsCard({ title, value, subtitle }: StatsCardProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <p className="text-sm text-gray-500">{title}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );
}
```

**Step 2: Write MoodChart.tsx**

```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface MoodPoint {
  score: number;
  created_at: number;
}

export default function MoodChart({ data }: { data: MoodPoint[] }) {
  const formatted = data.map(d => ({
    ...d,
    date: new Date(d.created_at * 1000).toLocaleDateString(),
  }));

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-medium text-gray-700 mb-4">Mood Trend (30d)</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={formatted}>
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis domain={[1, 10]} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 3: Write Dashboard.tsx**

```tsx
import { useEffect, useState } from 'react';
import api from '../api';
import StatsCard from '../components/StatsCard';
import MoodChart from '../components/MoodChart';

interface DashboardData {
  total_users: number;
  active_today: number;
  avg_mood_7d: number;
  tokens_today: { input: number; output: number };
  status_counts: Record<string, number>;
  mood_trend: { score: number; created_at: number }[];
  recent_messages: { user_id: number; role: string; content: string; created_at: number }[];
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    api<DashboardData>('/api/dashboard').then(setData);
  }, []);

  if (!data) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 mb-6">Dashboard</h2>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatsCard title="Total Users" value={data.total_users} />
        <StatsCard title="Active Today" value={data.active_today} />
        <StatsCard title="Avg Mood (7d)" value={data.avg_mood_7d} subtitle="out of 10" />
        <StatsCard
          title="Tokens Today"
          value={(data.tokens_today.input + data.tokens_today.output).toLocaleString()}
          subtitle={`in: ${data.tokens_today.input.toLocaleString()} / out: ${data.tokens_today.output.toLocaleString()}`}
        />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <MoodChart data={data.mood_trend} />
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-medium text-gray-700 mb-4">User Statuses</h3>
          {Object.entries(data.status_counts).map(([status, count]) => (
            <div key={status} className="flex justify-between py-1">
              <span className="text-sm text-gray-600 capitalize">{status}</span>
              <span className="text-sm font-medium">{count}</span>
            </div>
          ))}
          {Object.keys(data.status_counts).length === 0 && (
            <p className="text-sm text-gray-400">No users yet</p>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-4">Recent Messages</h3>
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {data.recent_messages.map((m, i) => (
            <div key={i} className="flex gap-3 text-sm">
              <span className="text-gray-400 w-16 shrink-0">
                {m.role === 'user' ? '👤' : '🤖'} {m.user_id}
              </span>
              <span className="text-gray-700 truncate">{m.content}</span>
              <span className="text-gray-400 text-xs ml-auto shrink-0">
                {new Date(m.created_at * 1000).toLocaleTimeString()}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add packages/admin-ui/src/
git commit -m "feat: add Dashboard page with stats, mood chart, recent messages"
```

---

### Task 8: Users list + User detail pages

**Files:**
- Create: `packages/admin-ui/src/pages/Users.tsx`
- Create: `packages/admin-ui/src/pages/UserDetail.tsx`
- Create: `packages/admin-ui/src/components/MessageList.tsx`

**Step 1: Write Users.tsx**

```tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';

interface User {
  user_id: number;
  status: string;
  missed_checkins: number;
  checkin_interval: number;
  last_message_at: number;
  last_mood: number | null;
}

export default function Users() {
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    api<User[]>('/api/users').then(setUsers);
  }, []);

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 mb-6">Users</h2>
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">User ID</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Status</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Last Mood</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Missed</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Interval</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Last Active</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.user_id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-3">
                  <Link to={`/users/${u.user_id}`} className="text-blue-600 hover:underline">
                    {u.user_id}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    u.status === 'stable' ? 'bg-green-100 text-green-700' :
                    u.status === 'monitoring' ? 'bg-yellow-100 text-yellow-700' :
                    u.status === 'active_support' ? 'bg-red-100 text-red-700' :
                    'bg-gray-100 text-gray-600'
                  }`}>
                    {u.status}
                  </span>
                </td>
                <td className="px-4 py-3">{u.last_mood ?? '—'}/10</td>
                <td className="px-4 py-3">{u.missed_checkins}</td>
                <td className="px-4 py-3">{u.checkin_interval}h</td>
                <td className="px-4 py-3 text-gray-400">
                  {new Date(u.last_message_at * 1000).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {users.length === 0 && (
          <p className="text-center text-gray-400 py-8">No users yet</p>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Write MessageList.tsx**

```tsx
interface Msg {
  role: string;
  content: string;
  created_at: number;
}

export default function MessageList({ messages }: { messages: Msg[] }) {
  return (
    <div className="space-y-3 max-h-[500px] overflow-y-auto">
      {messages.map((m, i) => (
        <div
          key={i}
          className={`flex flex-col ${m.role === 'user' ? 'items-start' : 'items-end'}`}
        >
          <div
            className={`max-w-[75%] rounded-xl px-4 py-2 text-sm ${
              m.role === 'user'
                ? 'bg-gray-100 text-gray-800'
                : 'bg-blue-500 text-white'
            }`}
          >
            {m.content}
          </div>
          <span className="text-xs text-gray-400 mt-1">
            {new Date(m.created_at * 1000).toLocaleTimeString()}
          </span>
        </div>
      ))}
    </div>
  );
}
```

**Step 3: Write UserDetail.tsx**

```tsx
import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api';
import MoodChart from '../components/MoodChart';
import MessageList from '../components/MessageList';

interface UserState {
  user_id: number;
  status: string;
  checkin_interval: number;
  missed_checkins: number;
  quiet_start: number;
  quiet_end: number;
}

export default function UserDetail() {
  const { id } = useParams();
  const [user, setUser] = useState<UserState | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [moods, setMoods] = useState<any[]>([]);

  useEffect(() => {
    if (!id) return;
    api<UserState>(`/api/users/${id}`).then(setUser);
    api<any[]>(`/api/messages/${id}?limit=100`).then(setMessages);
    api<any[]>(`/api/moods/${id}?days=90`).then(setMoods);
  }, [id]);

  const resetCheckins = async () => {
    await api(`/api/users/${id}/reset-checkins`, { method: 'POST' });
    setUser(prev => prev ? { ...prev, missed_checkins: 0 } : prev);
  };

  const updateInterval = async (interval: number) => {
    await api(`/api/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ checkin_interval: interval }),
    });
    setUser(prev => prev ? { ...prev, checkin_interval: interval } : prev);
  };

  if (!user) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <Link to="/users" className="text-sm text-blue-600 hover:underline mb-4 inline-block">
        ← Back to users
      </Link>
      <h2 className="text-xl font-bold text-gray-800 mb-6">User {user.user_id}</h2>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border p-4">
          <p className="text-sm text-gray-500">Status</p>
          <p className="text-lg font-medium capitalize">{user.status}</p>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <p className="text-sm text-gray-500">Check-in Interval</p>
          <p className="text-lg font-medium">{user.checkin_interval}h</p>
          <div className="flex gap-1 mt-2">
            {[2, 4, 8, 24].map(h => (
              <button
                key={h}
                onClick={() => updateInterval(h)}
                className={`px-2 py-1 text-xs rounded ${
                  user.checkin_interval === h
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 hover:bg-gray-200'
                }`}
              >
                {h}h
              </button>
            ))}
          </div>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <p className="text-sm text-gray-500">Missed Check-ins</p>
          <p className="text-lg font-medium">{user.missed_checkins}</p>
          <button
            onClick={resetCheckins}
            className="mt-2 text-xs text-blue-600 hover:underline"
          >
            Reset counter
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <MoodChart data={moods} />
        <div className="bg-white rounded-xl border p-5">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Quiet Hours</h3>
          <p className="text-sm text-gray-600">
            {user.quiet_start}:00 — {user.quiet_end}:00
          </p>
        </div>
      </div>

      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-4">
          Conversation ({messages.length} messages)
        </h3>
        <MessageList messages={messages} />
      </div>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add packages/admin-ui/src/
git commit -m "feat: add Users list and UserDetail pages with mood chart"
```

---

### Task 9: Agent Editor page

**Files:**
- Create: `packages/admin-ui/src/pages/AgentEditor.tsx`
- Create: `packages/admin-ui/src/components/YamlEditor.tsx`

**Step 1: Write YamlEditor.tsx**

```tsx
import { useState } from 'react';

interface YamlEditorProps {
  content: string;
  onSave: (content: string) => Promise<void>;
}

export default function YamlEditor({ content, onSave }: YamlEditorProps) {
  const [value, setValue] = useState(content);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      await onSave(value);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <textarea
        value={value}
        onChange={e => setValue(e.target.value)}
        className="w-full h-[500px] font-mono text-sm border border-gray-300 rounded-lg p-4 bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
        spellCheck={false}
      />
      <div className="flex items-center gap-3 mt-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save & Validate'}
        </button>
        {saved && <span className="text-sm text-green-600">Saved!</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  );
}
```

**Step 2: Write AgentEditor.tsx**

```tsx
import { useEffect, useState } from 'react';
import api from '../api';
import YamlEditor from '../components/YamlEditor';

const LAYERS = ['soul', 'role', 'tools', 'guardrails', 'memory', 'workflow'];

export default function AgentEditor() {
  const [activeTab, setActiveTab] = useState('soul');
  const [layers, setLayers] = useState<Record<string, string>>({});
  const [prompt, setPrompt] = useState('');
  const [showPrompt, setShowPrompt] = useState(false);

  useEffect(() => {
    api<{ layers: Record<string, string> }>('/api/agent/pack').then(d => setLayers(d.layers));
  }, []);

  const handleSave = async (content: string) => {
    const resp = await fetch(`/api/agent/pack/${activeTab}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('admin_token') || 'dev-token-change-me'}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ content }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Validation failed');
    }
    setLayers(prev => ({ ...prev, [activeTab]: content }));
  };

  const previewPrompt = async () => {
    const data = await api<{ prompt: string }>('/api/agent/prompt-preview');
    setPrompt(data.prompt);
    setShowPrompt(true);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">Agent Pack Editor</h2>
        <button
          onClick={previewPrompt}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200"
        >
          Preview System Prompt
        </button>
      </div>

      {showPrompt && (
        <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-xl p-5">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-sm font-medium text-yellow-800">System Prompt Preview</h3>
            <button onClick={() => setShowPrompt(false)} className="text-sm text-yellow-600 hover:underline">
              Close
            </button>
          </div>
          <pre className="text-sm text-gray-700 whitespace-pre-wrap">{prompt}</pre>
        </div>
      )}

      <div className="flex gap-1 mb-4 border-b">
        {LAYERS.map(layer => (
          <button
            key={layer}
            onClick={() => setActiveTab(layer)}
            className={`px-4 py-2 text-sm capitalize ${
              activeTab === layer
                ? 'border-b-2 border-blue-500 text-blue-600 font-medium'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {layer}
          </button>
        ))}
      </div>

      {layers[activeTab] !== undefined ? (
        <YamlEditor
          key={activeTab}
          content={layers[activeTab]}
          onSave={handleSave}
        />
      ) : (
        <p className="text-gray-400">Loading...</p>
      )}
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add packages/admin-ui/src/
git commit -m "feat: add Agent Pack Editor with YAML editing and prompt preview"
```

---

### Task 10: Monitoring + Settings pages

**Files:**
- Create: `packages/admin-ui/src/pages/Monitoring.tsx`
- Create: `packages/admin-ui/src/pages/Settings.tsx`

**Step 1: Write Monitoring.tsx**

```tsx
import { useEffect, useState } from 'react';
import api from '../api';
import StatsCard from '../components/StatsCard';

interface TokenEntry {
  user_id: number;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  created_at: number;
}

interface Summary {
  today: { input_tokens: number; output_tokens: number; cost: number };
  week: { input_tokens: number; output_tokens: number; cost: number };
  month: { input_tokens: number; output_tokens: number; cost: number };
}

export default function Monitoring() {
  const [tokens, setTokens] = useState<TokenEntry[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    api<TokenEntry[]>('/api/monitoring/tokens?days=30').then(setTokens);
    api<Summary>('/api/monitoring/summary').then(setSummary);
  }, []);

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 mb-6">Monitoring</h2>

      {summary && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatsCard title="Today" value={`$${summary.today.cost}`}
            subtitle={`${(summary.today.input_tokens + summary.today.output_tokens).toLocaleString()} tokens`} />
          <StatsCard title="This Week" value={`$${summary.week.cost}`}
            subtitle={`${(summary.week.input_tokens + summary.week.output_tokens).toLocaleString()} tokens`} />
          <StatsCard title="This Month" value={`$${summary.month.cost}`}
            subtitle={`${(summary.month.input_tokens + summary.month.output_tokens).toLocaleString()} tokens`} />
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Time</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">User</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Model</th>
              <th className="text-right px-4 py-3 text-gray-500 font-medium">Input</th>
              <th className="text-right px-4 py-3 text-gray-500 font-medium">Output</th>
              <th className="text-right px-4 py-3 text-gray-500 font-medium">Cost</th>
            </tr>
          </thead>
          <tbody>
            {tokens.map((t, i) => (
              <tr key={i} className="border-b">
                <td className="px-4 py-2 text-gray-400">
                  {new Date(t.created_at * 1000).toLocaleString()}
                </td>
                <td className="px-4 py-2">{t.user_id}</td>
                <td className="px-4 py-2 text-gray-600">{t.model.split('-').slice(-2).join('-')}</td>
                <td className="px-4 py-2 text-right">{t.input_tokens.toLocaleString()}</td>
                <td className="px-4 py-2 text-right">{t.output_tokens.toLocaleString()}</td>
                <td className="px-4 py-2 text-right">${t.cost}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {tokens.length === 0 && (
          <p className="text-center text-gray-400 py-8">No token usage yet</p>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Write Settings.tsx**

```tsx
import { useEffect, useState } from 'react';
import api from '../api';

export default function Settings() {
  const [config, setConfig] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api<Record<string, string>>('/api/config').then(setConfig);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const { TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY, ...safe } = config;
    await api('/api/config', { method: 'PATCH', body: JSON.stringify(safe) });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const editableKeys = [
    'CLAUDE_MODEL', 'ELEVENLABS_VOICE_ID', 'ELEVENLABS_MODEL',
    'CHECKIN_INTERVAL_HOURS', 'QUIET_HOURS_START', 'QUIET_HOURS_END',
    'ALLOWED_USER_IDS',
  ];

  const secretKeys = ['TELEGRAM_BOT_TOKEN', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'ELEVENLABS_API_KEY'];

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 mb-6">Settings</h2>

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-4">Bot Configuration</h3>
        <div className="space-y-4">
          {editableKeys.map(key => (
            <div key={key} className="flex items-center gap-4">
              <label className="w-56 text-sm text-gray-600">{key}</label>
              <input
                value={config[key] || ''}
                onChange={e => setConfig(prev => ({ ...prev, [key]: e.target.value }))}
                className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-3 mt-6">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
          {saved && <span className="text-sm text-green-600">Saved!</span>}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-sm font-medium text-gray-700 mb-4">API Keys (read-only)</h3>
        <div className="space-y-3">
          {secretKeys.map(key => (
            <div key={key} className="flex items-center gap-4">
              <label className="w-56 text-sm text-gray-600">{key}</label>
              <span className="text-sm text-gray-400">{config[key] || '—'}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add packages/admin-ui/src/
git commit -m "feat: add Monitoring and Settings pages"
```

---

## Phase 3: Launch & Verify

### Task 11: Launch scripts

**Files:**
- Create: `packages/admin-api/run.sh`
- Modify: `packages/telegram-bot/.env` (add ADMIN_TOKEN)

**Step 1: Write admin API run script**

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export DB_PATH="../telegram-bot/data/wellness.db"
export PACK_DIR="../../packs/wellness-cbt"
export ENV_PATH="../telegram-bot/.env"
export ADMIN_TOKEN="${ADMIN_TOKEN:-dev-token-change-me}"

echo "Starting Admin API on :8080..."
python3 -m uvicorn admin_api.app:app --host 0.0.0.0 --port 8080 --reload
```

**Step 2: Make executable**

```bash
chmod +x packages/admin-api/run.sh
```

**Step 3: Add ADMIN_TOKEN to .env**

Add to `packages/telegram-bot/.env`:

```
ADMIN_TOKEN=dev-token-change-me
```

**Step 4: Commit**

```bash
git add packages/admin-api/run.sh packages/telegram-bot/.env
git commit -m "feat: add admin API launch script"
```

---

### Task 12: Final verification

**Step 1: Run all telegram-bot tests**

```bash
cd packages/telegram-bot
python3 -m pytest tests/ -v --tb=short
```

Expected: All tests pass (including new token tracking tests)

**Step 2: Run admin-api tests**

```bash
cd packages/admin-api
python3 -m pytest tests/ -v --tb=short
```

Expected: All tests pass

**Step 3: Run agent-core tests**

```bash
cd packages/agent-core
python3 -m pytest tests/ -v --tb=short -q
```

Expected: 296 tests pass (unchanged)

**Step 4: Start admin API and verify endpoints**

```bash
cd packages/admin-api
./run.sh &
curl -s -H "Authorization: Bearer dev-token-change-me" http://localhost:8080/api/health
curl -s -H "Authorization: Bearer dev-token-change-me" http://localhost:8080/api/dashboard
```

**Step 5: Start admin UI and verify**

```bash
cd packages/admin-ui
npm run dev
# Open http://localhost:5173 in browser
```

**Step 6: Final commit**

```bash
git commit -m "chore: admin panel complete — all tests passing"
```
