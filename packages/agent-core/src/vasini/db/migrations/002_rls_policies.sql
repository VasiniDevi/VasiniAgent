-- Migration 002: Row-Level Security (RLS) Policies
-- Enforces tenant isolation at the database level.
-- Every query MUST first: SET LOCAL app.tenant_id = '<uuid>';
--
-- FORCE RLS ensures even table owners are subject to policies.

-- ============================================================
-- Helper: Create RLS policy for a table
-- Pattern: tenant_id = current_setting('app.tenant_id')::uuid
-- ============================================================

-- Agents
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_agents ON agents
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Tasks
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_tasks ON tasks
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Tool Executions
ALTER TABLE tool_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_executions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_tool_executions ON tool_executions
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Audit Log
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_audit_log ON audit_log
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Memory Factual
ALTER TABLE memory_factual ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_factual FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_memory_factual ON memory_factual
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Memory Episodic
ALTER TABLE memory_episodic ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_episodic FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_memory_episodic ON memory_episodic
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Event Outbox
ALTER TABLE event_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_event_outbox ON event_outbox
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Idempotency Keys
ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_keys FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_idempotency_keys ON idempotency_keys
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Inbox Events
ALTER TABLE inbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbox_events FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_inbox_events ON inbox_events
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
