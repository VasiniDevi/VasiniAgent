-- Migration 001: Initial Schema
-- Creates all tenant-scoped tables for the Vasini Agent Framework.
-- Requires PostgreSQL 15+ with pgvector extension.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- Agents
-- ============================================================
CREATE TABLE IF NOT EXISTS agents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL,
    pack_id     VARCHAR(128) NOT NULL,
    pack_version VARCHAR(32) NOT NULL,
    session_id  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_agents_tenant_id ON agents (tenant_id);
CREATE INDEX IF NOT EXISTS ix_agents_tenant_pack ON agents (tenant_id, pack_id);

-- ============================================================
-- Tasks
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    agent_id        UUID NOT NULL REFERENCES agents(id),
    state           VARCHAR(16) NOT NULL DEFAULT 'queued',
    input_text      TEXT NOT NULL,
    output_text     TEXT,
    idempotency_key VARCHAR(64) NOT NULL UNIQUE,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    heartbeat_at    TIMESTAMPTZ,
    CONSTRAINT chk_task_state CHECK (state IN ('queued', 'running', 'retry', 'done', 'failed', 'cancelled', 'dead_letter'))
);

CREATE INDEX IF NOT EXISTS ix_tasks_tenant_id ON tasks (tenant_id);
CREATE INDEX IF NOT EXISTS ix_tasks_tenant_state ON tasks (tenant_id, state);
CREATE UNIQUE INDEX IF NOT EXISTS ix_tasks_idempotency ON tasks (idempotency_key);

-- ============================================================
-- Idempotency Keys
-- ============================================================
CREATE TABLE IF NOT EXISTS idempotency_keys (
    id              SERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    idempotency_key VARCHAR(64) NOT NULL,
    resource_type   VARCHAR(32) NOT NULL,
    resource_id     UUID NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_idempotency_tenant_key UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS ix_idempotency_tenant_key ON idempotency_keys (tenant_id, idempotency_key);

-- ============================================================
-- Inbox Events (at-least-once dedup)
-- ============================================================
CREATE TABLE IF NOT EXISTS inbox_events (
    event_id     UUID PRIMARY KEY,
    tenant_id    UUID NOT NULL,
    event_type   VARCHAR(128) NOT NULL,
    processed    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_inbox_events_tenant_id ON inbox_events (tenant_id);

-- ============================================================
-- Tool Executions
-- ============================================================
CREATE TABLE IF NOT EXISTS tool_executions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    task_id         UUID NOT NULL,
    tool_id         VARCHAR(128) NOT NULL,
    tool_name       VARCHAR(256) NOT NULL,
    arguments_json  TEXT NOT NULL,
    success         BOOLEAN NOT NULL,
    result_json     TEXT,
    error           TEXT,
    duration_ms     INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_tool_executions_tenant_id ON tool_executions (tenant_id);
CREATE INDEX IF NOT EXISTS ix_tool_exec_tenant_task ON tool_executions (tenant_id, task_id);

-- ============================================================
-- Audit Log
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id    UUID NOT NULL,
    action       VARCHAR(128) NOT NULL,
    actor        VARCHAR(256) NOT NULL,
    resource     VARCHAR(256) NOT NULL,
    details_json TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_audit_log_tenant_id ON audit_log (tenant_id);

-- ============================================================
-- Memory: Factual (versioned key-value)
-- ============================================================
CREATE TABLE IF NOT EXISTS memory_factual (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id  UUID NOT NULL,
    agent_id   UUID NOT NULL,
    key        VARCHAR(256) NOT NULL,
    value      TEXT NOT NULL,
    version    INTEGER NOT NULL DEFAULT 1,
    evidence   TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_memory_factual_tenant_id ON memory_factual (tenant_id);
CREATE INDEX IF NOT EXISTS ix_memory_factual_tenant_key ON memory_factual (tenant_id, agent_id, key);

-- ============================================================
-- Memory: Episodic (pgvector semantic search)
-- ============================================================
CREATE TABLE IF NOT EXISTS memory_episodic (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id  UUID NOT NULL,
    agent_id   UUID NOT NULL,
    content    TEXT NOT NULL,
    source     TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    embedding  vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_memory_episodic_tenant_id ON memory_episodic (tenant_id);
CREATE INDEX IF NOT EXISTS ix_memory_episodic_tenant_agent ON memory_episodic (tenant_id, agent_id);

-- ============================================================
-- Event Outbox (transactional outbox pattern)
-- ============================================================
CREATE TABLE IF NOT EXISTS event_outbox (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    event_type      VARCHAR(128) NOT NULL,
    event_data_json TEXT NOT NULL,
    published       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_event_outbox_tenant_id ON event_outbox (tenant_id);
CREATE INDEX IF NOT EXISTS ix_outbox_unpublished ON event_outbox (published, created_at);
