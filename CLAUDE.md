# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VasiniAgent is a multi-tenant AI agent framework with a composable 7-layer agent architecture (Soul, Role, Tools, Skills, Guardrails, Memory, Workflow). The primary deployment is a wellness CBT/MCT Telegram bot with a protocol engine that uses deterministic rules for practice selection and LLM only for dialogue generation.

## Monorepo Structure

- **packages/agent-core/** — Python. Agent runtime, LLM router, memory (Redis/pgvector/PostgreSQL), safety, policy engine, sandbox, finops. Source in `src/vasini/`.
- **packages/telegram-bot/** — Python. Telegram wellness bot with protocol engine (FSM states, safety classifier, rule engine, practice runner, LLM adapter). Source in `src/wellness_bot/`.
- **packages/admin-api/** — Python. FastAPI admin backend.
- **packages/admin-ui/** — TypeScript/React. Vite + Tailwind admin dashboard.
- **packages/gateway/** — TypeScript. Fastify server, gRPC client, BullMQ task queue.
- **packs/wellness-cbt/** — YAML profession pack (soul, role, tools, guardrails, memory, workflow, practices/).
- **proto/** — gRPC protobuf definitions (`vasini/agent/v1/agent.proto`).
- **schemas/** — JSON Schema validators for pack components.
- **docs/plans/** — Architecture design docs and implementation plans.

## Build & Run Commands

```bash
make setup              # Install agent-core[dev] + gateway deps (pnpm)
make dev                # Start PostgreSQL (pgvector) + Redis via docker compose

make test               # Run all tests (Python + TypeScript)
make test-core          # pytest -v --cov=vasini (agent-core)
make test-gateway       # pnpm test (gateway, vitest)

make lint               # Run all linters
make lint-core          # ruff check + mypy (agent-core)
make lint-gateway       # eslint (gateway)

make proto              # Compile gRPC protobuf definitions
```

### Running a single test

```bash
# Python (agent-core or telegram-bot)
cd packages/agent-core && pytest tests/test_composer.py -v
cd packages/agent-core && pytest tests/test_composer.py::test_function_name -v
cd packages/telegram-bot && pytest tests/test_protocol_engine.py -v

# TypeScript (gateway)
cd packages/gateway && pnpm test path/to/test.test.ts
```

### Running individual packages

```bash
cd packages/telegram-bot && python -m wellness_bot.app
cd packages/admin-api && uvicorn admin_api.app:app --reload
cd packages/gateway && pnpm dev
cd packages/admin-ui && pnpm dev
```

## Code Style

- **Python**: ruff (line-length 120, target py312) + mypy. Pydantic v2 for models. asyncio_mode = "auto" in pytest.
- **TypeScript**: ESLint. Vitest for tests.
- **Build system**: Hatchling for all Python packages.

## Architecture: Protocol Engine (telegram-bot)

The wellness bot's protocol engine is a 7-module pipeline:

1. **Handler** (`handlers.py`) — Telegram message → SessionContext
2. **SafetyClassifier** (`protocol/safety.py`) — Hard rules layer + Haiku LLM escalation
3. **ProtocolEngine** (`protocol/engine.py`) — FSM with whitelisted state transitions (SAFETY_CHECK → INTAKE → ASSESSMENT → PRACTICE_INTRO → PRACTICE_ACTIVE → REFLECTION → SESSION_END)
4. **RuleEngine** (`protocol/rules.py`) — Deterministic practice selection: distress level + session cycle → ranked practice list
5. **PracticeRunner** — Executes YAML practice definitions step-by-step (with timers, buttons, text input)
6. **LLM Adapter** (`protocol/llm_adapter.py`) — Text generation per LLMContract, response validation, circuit breaker
7. **ProgressTracker** — Session/assessment/safety event logging to SQLite

Key design: **deterministic rules select practices, LLM only generates dialogue text**. Safety classifier gates every message before processing.

## Architecture: Agent-Core

- **Composer** (`composer.py`) — Assembles AgentConfig from YAML+Markdown profession packs using the 7-layer model
- **LLM Router** (`llm/`) — Anthropic Claude provider with cost/latency routing and fallback chains
- **Runtime** (`runtime/`) — Agent execution loop with state machine (QUEUED → RUNNING → DONE/FAIL/CANCELLED/DEAD_LETTER)
- **Memory** (`memory/`) — Short-term (Redis TTL), episodic (pgvector), factual (PostgreSQL append-only)
- **Events** (`events/`) — CloudEvents 1.0 over Redis Streams (Kafka migration path)
- **Safety** (`safety/`) — 3-tier: hard rules → model classification → human escalation
- **Policy** (`policy/`) — RBAC/ABAC with OPA integration
- **DB** (`db/`) — SQLAlchemy with Row-Level Security for multi-tenant isolation

## Infrastructure

- **PostgreSQL 16** with pgvector extension (docker-compose, port 5432)
- **Redis 7** with 3 logical databases, persistence enabled (port 6379)
- Multi-tenancy via Row-Level Security at DB level, tenant context threaded through all layers
- gRPC for production transport, HTTP+JSON for development (same protobuf envelope)

## Practice YAML Files

Located at `packs/wellness-cbt/practices/`. Each YAML defines a therapeutic practice with metadata, steps (UI modes: text/buttons/timer/text_input), pre/post-rating scales, and fallback logic. The practice_loader (`protocol/practice_loader.py`) validates these with fail-fast semantics.
