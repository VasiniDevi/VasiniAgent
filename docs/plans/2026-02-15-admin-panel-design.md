# Wellness Agent Admin Panel — Design Document

**Date:** 2026-02-15
**Status:** Approved
**Goal:** Full admin panel for the Wellness CBT Telegram Agent — user monitoring, agent pack editing, token/cost monitoring, bot settings.

---

## 1. Overview

A web-based admin panel for a single admin to manage the wellness bot. FastAPI backend (Python) shares the same SQLite database as the running bot. React SPA frontend with Tailwind + shadcn/ui + Recharts for charts.

### Audience
- Single admin (bearer token auth)

### Tech Decisions
- **Backend:** FastAPI (Python), shares SQLite with bot
- **Frontend:** Vite + React + TypeScript + Tailwind + shadcn/ui + Recharts
- **Auth:** Single bearer token from `.env` (`ADMIN_TOKEN`)
- **Pack editing:** Read/write YAML files, validate via Composer before save

---

## 2. Architecture

```
┌─────────────────────────────────────────────────┐
│                 Browser (React SPA)              │
│  Vite + React + Tailwind + shadcn/ui + Recharts │
│                                                  │
│  Pages:                                          │
│  /dashboard    — overview: users, mood, activity │
│  /users        — list + user details             │
│  /users/:id    — dialogs, mood chart, settings   │
│  /agent        — pack editor (soul/role/guards)  │
│  /agent/prompt — preview system prompt           │
│  /monitoring   — logs, costs, events             │
│  /settings     — bot config, quiet hours         │
└──────────────────────┬──────────────────────────┘
                       │ HTTP (localhost:3000 → :8080)
┌──────────────────────▼──────────────────────────┐
│              FastAPI Backend (:8080)              │
│                                                  │
│  /api/dashboard   — stats summary                │
│  /api/users       — list, detail, state          │
│  /api/messages    — conversation history         │
│  /api/moods       — mood data + trends           │
│  /api/agent/pack  — read/update YAML layers      │
│  /api/agent/prompt— preview system prompt        │
│  /api/monitoring  — token usage, costs           │
│  /api/config      — bot settings                 │
│                                                  │
│  Auth: Bearer token (single admin)               │
│  Reads: SQLite (same DB as bot)                  │
│  Reads/Writes: Pack YAML files                   │
│  Reads: Composer + AgentRuntime (prompt preview) │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     SQLite DB    Pack YAMLs   Bot Process
     (shared)     (filesystem) (running)
```

---

## 3. Pages & Functionality

### Dashboard (`/dashboard`)
- **Cards:** total users, active today, avg mood 7d, tokens spent
- **Mood trend** — line chart 7/30 days (Recharts)
- **Recent messages** — last 10 messages from all users
- **User statuses** — count by onboarding / stable / monitoring / active_support

### Users (`/users` → `/users/:id`)
- **List:** id, status, last message, current mood, missed checkins
- **Detail:**
  - Mood chart (score history with notes)
  - Conversation history (scrollable, searchable)
  - State: status, checkin interval, missed checkins, quiet hours
  - Actions: change interval, reset missed, pause/resume checkins

### Agent Pack Editor (`/agent`)
- **Tabs:** Soul | Role | Tools | Guardrails | Memory | Workflow
- YAML editor per tab (textarea with monospace)
- **Preview Prompt** — shows assembled system prompt
- **Save** — validates via Composer.load() before writing
- Validation errors shown inline

### Monitoring (`/monitoring`)
- **Token usage** — table: date, model, input/output tokens, cost
- **Aggregated** — totals per day/week/month
- **Event logs** — recent bot actions (responses, checkins, errors)

### Settings (`/settings`)
- Current bot config display (safe fields, no API keys)
- Editable: claude_model, elevenlabs_voice_id, checkin_interval, quiet_hours
- Save to `.env` file

---

## 4. API Endpoints

```
Auth: Header "Authorization: Bearer {ADMIN_TOKEN}"

GET    /api/dashboard                        → stats summary
GET    /api/users                            → user list
GET    /api/users/:id                        → user detail + state
PATCH  /api/users/:id                        → update user state
POST   /api/users/:id/reset-checkins         → reset missed counter

GET    /api/messages/:user_id?limit=50       → conversation history
GET    /api/moods/:user_id?days=30           → mood entries

GET    /api/agent/pack                       → all layers as YAML
GET    /api/agent/pack/:layer                → single layer YAML
PUT    /api/agent/pack/:layer                → save + validate YAML
GET    /api/agent/prompt-preview             → assembled system prompt

GET    /api/monitoring/tokens?days=30        → token usage entries
GET    /api/monitoring/summary               → aggregated costs

GET    /api/config                           → bot config (safe fields)
PATCH  /api/config                           → update config
```

---

## 5. Token Tracking (new)

Add `token_usage` table to existing SQLite:

```sql
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at REAL
);
```

Save `response.usage` after each `provider.chat()` call in handlers.

---

## 6. Package Structure

```
packages/admin-api/          # FastAPI backend
├── pyproject.toml
├── src/admin_api/
│   ├── __init__.py
│   ├── app.py               # FastAPI app + CORS + auth
│   ├── auth.py               # Bearer token middleware
│   ├── routes/
│   │   ├── dashboard.py
│   │   ├── users.py
│   │   ├── messages.py
│   │   ├── moods.py
│   │   ├── agent.py
│   │   ├── monitoring.py
│   │   └── config.py
│   └── deps.py               # shared dependencies (db, paths)
└── tests/

packages/admin-ui/           # React SPA
├── package.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api.ts
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Users.tsx
│   │   ├── UserDetail.tsx
│   │   ├── AgentEditor.tsx
│   │   ├── Monitoring.tsx
│   │   └── Settings.tsx
│   └── components/
│       ├── Layout.tsx
│       ├── MoodChart.tsx
│       ├── MessageList.tsx
│       ├── StatsCard.tsx
│       └── YamlEditor.tsx
```
