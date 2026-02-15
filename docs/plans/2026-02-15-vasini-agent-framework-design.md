# Vasini Agent Framework — Design Document v3.3

**Date:** 2026-02-15
**Status:** Approved
**Approach:** Composable Soul
**Stack:** Python (Agent Core) + TypeScript (Gateway) + gRPC + Redis Streams + PostgreSQL + pgvector

---

## 1. Architecture Overview

### Microservice Structure

```
Gateway (TypeScript)
  REST/WS API, Auth (OIDC), Rate Limiting, Tenant Resolution, mTLS
  Channels: Telegram, Slack, Discord, Web, API
  Correlation: trace_id + tenant_id + agent_id + pack_version
       │
       │ gRPC (Protobuf versioned)
       ▼
Agent Core (Python)
  ├── Composer        — Assembles agent from composable layers, merge-order, conflict resolution, schema validation
  ├── Runtime         — Agent loop + State Machine (QUEUED→RUNNING→RETRY→DONE/FAIL/CANCELLED/DEAD_LETTER) + heartbeat/lease + idempotency keys
  ├── LLM Router      — Cost/latency/quality routing by tier, fallback chain, circuit breaker, per-tenant budget caps
  ├── Tool Sandbox    — Ephemeral creds, egress policy per tool, timeout + resource limits, allow/denylist, network perimeter, audit trail
  ├── Policy Engine   — RBAC/ABAC runtime enforcement, OPA policy-as-code, HITL approval checkpoints for high-risk actions
  └── Memory Manager
        ├── Short-term  (Redis, TTL-based)
        ├── Episodic/Semantic (pgvector, confidence threshold for write)
        └── Factual/Source-of-Truth (PostgreSQL, append-only versioned, PII classification, GDPR delete)
       │
       ├── Control Plane       — Single source of truth, version management, rollout/canary/rollback, feature flags, release flow: draft→validated→staged→prod, no bypass publishing
       ├── Trust & Safety      — Prompt Firewall (input sanitization, jailbreak detectors, output policy checks), Retrieval Trust (source allowlist, trust scoring, data poisoning defense), Content Filters (PII detection, toxicity)
       ├── Pack Registry       — Sigstore/cosign signed, immutable artifacts, SBOM + provenance, compatibility matrix, release lifecycle
       ├── Evaluation Service  — OFFLINE: golden datasets, quality gates, hallucination detection, regression tests. ONLINE: drift detection, live guardrails, SLO per tenant + pack
       ├── Identity & Secrets  — OIDC users/tenants, mTLS service-to-service, Vault/KMS, secret isolation per agent/tenant, ephemeral credential rotation
       ├── Schema Registry     — Protobuf (backward), CloudEvents (backward transitive), Pack JSON Schema (full CI validation). CI gate: compatibility check on PR. N-1 support: 3 months
       │
       ▼
Event Bus (async, pub/sub — facts only)
  Redis Streams (start) → Kafka (SLO-triggered migration)
  At-least-once + idempotent consumers
  Outbox pattern (PG→bus), Inbox/idempotency table at consumer
  DLQ + replay console
  Event schema versioning (CloudEvents 1.0 spec)
  Events: agent.created, agent.completed, tool.executed, tool.failed, eval.passed, eval.failed, pack.published, policy.violated, model.fallback, budget.exceeded, tenant.created

Commands (point-to-point, queue/RPC)
  gRPC / Task Queue (Redis + BullMQ)
  Commands: agent.create, tool.execute, pack.publish, eval.run
  At-least-once + idempotent handler (dedup by idempotency_key)

FinOps & Cost Governance
  Token accounting per tenant/agent/model
  Budget caps: soft (alert) + hard (stop)
  Per-tool quotas, model spend routing
  Cost dashboards + anomaly alerts

Infrastructure
  PostgreSQL (state, tenants, factual memory, outbox table)
    └── Row-Level Security (RLS) — default for multi-tenant
  Redis (logically separated: cache / queue / streams)
  pgvector (episodic/semantic memory, tenant-isolated)
  OpenTelemetry (trace_id + agent_id + tenant_id + pack_version)
  Temporal (workflow engine for multi-step tasks >3 steps or >1 compensating action)
```

---

## 2. Key Architectural Decisions

### 2.1 Event Model — Commands vs Events

```yaml
# Commands (imperative, point-to-point, queue/RPC):
#   agent.create, tool.execute, pack.publish, eval.run

# Events (past tense, pub/sub, fact):
#   agent.created, tool.executed, pack.published, eval.passed

# Event envelope: CloudEvents 1.0
# specversion: "1.0"
# type: "ai.vasini.agent.completed"
# source: "/agent-core/runtime"
# subject: "agent:senior-python-dev:run-4821"
# id: "evt-uuid"
# time: ISO 8601
# datacontenttype: "application/json"
# dataschema: "https://registry.vasini.ai/schemas/agent.completed/v1.json"

# Versioning rules:
# - Additive fields = same version
# - Breaking changes = new major version
# - N-1 support: 3 months
```

### 2.2 Tenant Isolation — RLS with Full DB-Role Model

```sql
-- Three roles, strictly separated:

-- 1. app_role: ONLY used by application. NOT superuser, NOT owner.
CREATE ROLE app_role NOINHERIT NOSUPERUSER;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_role;

-- 2. migration_role: ONLY for schema migrations (CI/CD pipeline).
CREATE ROLE migration_role NOINHERIT NOSUPERUSER;
GRANT USAGE, CREATE ON SCHEMA public TO migration_role;
-- ALTER/DROP via ownership: migration_role = owner of all tables

-- 3. superuser: NEVER used by application.
--    Access only for DBA via separate bastion + MFA.
--    Monitoring: alert on any superuser connection from non-bastion IP.

-- FORCE RLS on ALL tenant tables:
-- agents, tasks, memory_factual, memory_episodic, tool_executions, audit_log, packs

-- Safe tenant context check:
-- current_setting('app.tenant_id', true) — returns NULL instead of error

-- PgBouncer: transaction pooling mode
-- ALL DB operations inside explicit transactions (BEGIN/COMMIT)
-- SET LOCAL app.tenant_id = '<uuid>' at start of every transaction
-- Trigger guard: RAISE EXCEPTION if tenant_id IS NULL
```

**Migration to schema-per-tenant criteria:**
- Tenant requires dedicated compliance (HIPAA, SOC2 per-tenant)
- Tenant generates >30% of total load
- Regulatory requirement for physical data isolation

### 2.3 Memory Write Policy

```yaml
memory_policy:
  short_term:
    store: redis
    ttl: "24h"              # single TTL source of truth
    auto_write: true
    eviction: "lru"

  episodic:
    store: pgvector
    retention: "90d"         # per-tenant override via Control Plane
    confidence_threshold: 0.75
    source_required: true
    dedup: true
    pii_check: true

  factual:
    store: postgresql
    retention: "indefinite"
    model: "append-only versioned"  # NOT overwrite
    confidence_threshold: 0.95
    requires_evidence: true
    requires_approval: true  # for high-risk packs
    audit_log: true

  gdpr:
    delete_scope: "full_cascade"
    right_to_export: true
```

### 2.4 Release Policy

```
Stage      | Who promotes       | Requirements              | Automation
---------- | ------------------ | ------------------------- | ------------------
draft      | Author             | pack validate passes      | CI lint + schema
validated  | Eval System (auto) | Golden dataset score >=85 | Auto eval pipeline
staged     | Platform Engineer  | Canary OK, SLO met        | Auto-rollback if err >2x
prod       | Platform Lead      | Canary OK + sign-off      | Gradual 5→25→50→100%
```

Rollback: emergency by on-call (post-factum approval 24h, else freeze + mandatory review).

### 2.5 Incident Model

```yaml
SEV1_CRITICAL:   # Full outage or data breach
  response: 15min, rollback: automatic, notify: on-call + lead + security

SEV2_HIGH:       # Degradation >10% users
  response: 30min, rollback: auto if SLO breached >5min, notify: on-call + lead

SEV3_MEDIUM:     # Single tenant/pack degradation
  response: 2h, rollback: manual per-pack, notify: on-call

SEV4_LOW:        # Cosmetic, non-critical
  response: next business day, notify: ticket
```

SLO error budget: if exhausted in 30d window → freeze rollouts, redirect effort to reliability, resume when budget >20%.

---

## 3. Security

### 3.1 Encryption

```yaml
encryption:
  in_transit: "TLS 1.3 / mTLS between services"
  at_rest: "AES-256 (PG TDE / pgcrypto)"
  field_level:
    sensitive_fields: ["pii.*", "credentials.*", "memory.factual.content"]
    engine: "envelope encryption via KMS"
  key_hierarchy:
    master_key: "KMS-managed, never exported"
    tenant_key: "derived per tenant, stored encrypted in KMS"
    data_key: "ephemeral, per-operation envelope encryption"
  rotation: "data keys per operation, tenant keys 90d, master key 365d"
  revocation: "tenant key revoke → re-encrypt all tenant data with new key"
```

### 3.2 Model Governance

```yaml
model_governance:
  tier_classes:
    tier-1: "full capability models (e.g. opus-class)"
    tier-2: "balanced models (e.g. sonnet-class)"
    tier-3: "fast/cheap models (e.g. haiku-class)"
  # Mapping tier→model in Control Plane config
  per_tenant_allowlist: true
  per_pack_restrictions:
    high_risk_packs:
      min_tier: "tier-1"
      required_features: ["extended_thinking"]
    low_risk_packs:
      any_tier: true
  fallback_chain: "tier-1 → tier-2 → tier-3"
  circuit_breaker:
    error_threshold: 5
    window: "60s"
    half_open_after: "120s"
```

---

## 4. Reliability

### 4.1 Delivery Guarantees

- Commands: at-least-once + idempotent handler (dedup by idempotency_key)
- Events: at-least-once + idempotent consumer (dedup by event_id in inbox table)
- Outbox pattern: PG outbox table → poller → Event Bus
- Inbox pattern: inbox/idempotency table → dedup by event_id
- DLQ: max retries 5, exponential backoff, replay console

### 4.2 Task State Machine

```
QUEUED → RUNNING → DONE
              ├──→ RETRY (max 3, exp backoff) → FAILED → DEAD_LETTER
              ├──→ CANCELLED
              └──→ (timeout/heartbeat miss) → RETRY

Heartbeat/lease: worker must heartbeat every 30s, lease expires after 90s
Idempotency: idempotency_key per task, dedup on pickup
```

### 4.3 Infrastructure Requirements

```yaml
clock_sync:
  protocol: "NTP (chrony)"
  max_drift: "50ms between any two nodes"
  monitoring: "alert if drift > 100ms"

backup:
  postgresql: "daily full + hourly WAL archiving"
  rpo: "1h"
  rto: "4h"
  multi_az: true

drills:
  restore_drill: "quarterly"
  failover_drill: "quarterly"
  chaos_game_day: "monthly in staging"

kafka_migration_triggers:  # from Redis Streams
  - "consumer lag > 30s sustained"
  - "replay need > 7d"
  - "data loss risk > 0.01%"

redis_separation:
  - "redis-cache (DB 0)"
  - "redis-queue (DB 1)"
  - "redis-streams (DB 2)"
  # Separate clusters at scale
```

### 4.4 DB Schema Migrations

```yaml
strategy: "expand-contract"
rules:
  - "zero-downtime: no DROP/RENAME in expand phase"
  - "expand: add new columns/tables (nullable or with defaults)"
  - "migrate data in background"
  - "contract: remove old columns after all consumers migrated"
  - "backward compatible for N-1 app version"
```

### 4.5 Contract Testing

```yaml
grpc: "buf breaking --against .git#branch=main"
events: "consumer-driven contract tests"
ci_gate: "PR blocked if contract broken"
```

### 4.6 Chaos/Resilience Tests

```yaml
pre_prod_scenarios:
  - "Redis unavailable 30s → graceful degradation"
  - "LLM provider timeout → fallback chain"
  - "Vault sealed → no secret leaks in logs"
  - "VectorDB down → factual memory still works"
  - "PG replica lag 10s → read consistency"
cadence: "weekly in staging, before each major release"
```

---

## 5. Capacity & Cost Governance

```yaml
capacity:
  concurrency_limits:
    per_tenant: "configurable via Control Plane"
    per_pack: "configurable via Control Plane"
    per_tool: "configurable via Control Plane"
  backpressure: "429 Too Many Requests + Retry-After"

finops:
  token_accounting: "per tenant/agent/model"
  budget_caps:
    soft: "alert"
    hard: "stop execution"
  anomaly_detection: true

data_residency:
  default_region: "${ORG_DEFAULT_REGION}"  # org-level config
  per_tenant_override: true
```

---

## 6. Observability

```yaml
golden_signals:  # per service, per tenant
  latency: "histogram, p50/p95/p99"
  traffic: "requests per second"
  errors: "error rate %, by type"
  saturation: "CPU, memory, queue depth, connection pool"

correlation: "trace_id + tenant_id + agent_id + pack_version"
dashboards: "one per service, auto-generated from OTel"
```

### Target SLOs (by risk level)

| Metric              | Low Risk | Medium Risk | High Risk |
|----------------------|----------|-------------|-----------|
| Response p95         | < 5s     | < 8s        | < 15s     |
| Success rate         | > 98%    | > 99%       | > 99.5%   |
| Publish → prod       | < 2h     | < 4h        | < 24h     |
| Hallucination rate   | < 8%     | < 5%        | < 2%      |
| Canary duration      | 30min    | 1h          | 4h        |

---

## 7. Evaluation

```yaml
offline:  # pre-release quality gates
  golden_datasets: true
  regression_tests: true
  hallucination_detection: true
  min_score: 0.85

online:  # post-release monitoring
  drift_detection: true
  live_guardrails: true
  slo_tracking: true

shadow_mode:
  description: "New pack on real traffic without affecting response"
  flow:
    - "Real request → current prod pack → response to user"
    - "Same request → shadow pack → result to eval store"
    - "Diff analysis: quality, latency, cost"
  traffic: "configurable 1-100% via Control Plane"
  constraint: "shadow pack tools in read-only sandbox"
```

---

## 8. Composable Soul — Layer Specifications

### Merge Order (definitive)

```
Priority (lowest to highest):
  1. _shared/base/*          — platform defaults
  2. _shared/category/*      — profession category (tech, business, medical...)
  3. _shared/specialization/* — narrow specialization (backend, frontend, cardiology...)
  4. pack-level inline       — specific pack WINS

Conflict: same field at same priority level in two extends = CI ERROR
```

### Directory Structure

```
agents/
├── senior-python-dev/
│   ├── profession-pack.yaml   # Manifest — ties all layers
│   ├── SOUL.yaml
│   ├── ROLE.yaml
│   ├── TOOLS.yaml
│   ├── SKILLS/
│   │   ├── code-review.md
│   │   └── debugging.md
│   ├── GUARDRAILS.yaml
│   ├── MEMORY.yaml
│   └── WORKFLOW.yaml
│
├── _shared/
│   ├── base/
│   │   └── soul-base.yaml
│   ├── souls/
│   │   ├── professional.yaml
│   │   └── creative.yaml
│   ├── guardrails/
│   │   ├── safe-coding.yaml
│   │   └── no-pii.yaml
│   └── skills/
│       ├── git-workflow.md
│       └── testing.md
```

### 8.1 SOUL.yaml — Personality & Tone

Defines HOW the agent communicates. Does NOT affect tools or logic.

```yaml
soul:
  schema_version: "1.0"
  identity:
    name: string
    language: string
    languages: string[]
  personality:
    communication_style: enum    # formal | professional | casual | academic
    verbosity: enum              # concise | balanced | detailed
    proactivity: enum            # reactive | balanced | proactive
    confidence_expression: enum  # cautious | balanced | assertive
  tone:
    default: string
    on_success: string
    on_error: string
    on_uncertainty: string
  principles: string[]           # 3-7 behavioral principles
  adaptations:
    beginner_user: string
    expert_user: string
    crisis_mode: string
```

### 8.2 ROLE.yaml — Role, Goal, Competencies

Defines WHO the agent is and WHY it exists. Features competency graph.

```yaml
role:
  schema_version: "1.0"
  title: string
  domain: string
  seniority: enum                # junior | middle | senior | lead | principal
  goal:
    primary: string
    secondary: string[]
  backstory: string              # 2-5 sentences
  competency_graph:
    skills:
      - id: string
        name: string
        level: enum              # novice | competent | proficient | expert | master
        evidence: string[]
        tasks: string[]
        metrics:
          - name: string
            target: number
  domain_knowledge:
    primary: string[]
    secondary: string[]
  limitations: string[]          # what agent explicitly CANNOT do
```

### 8.3 TOOLS.yaml — Instruments

Defines WHAT the agent can use with per-tool sandbox config.

```yaml
tools:
  schema_version: "1.0"
  available:
    - id: string
      name: string
      description: string
      sandbox:
        timeout: duration
        memory_limit: string
        cpu_limit: string
        network: enum            # none | egress_allowlist | full
        egress_allowlist: string[]
        filesystem: enum         # none | read_only | read_write | scoped
        scoped_paths: string[]
      risk_level: enum           # low | medium | high | critical
      requires_approval: boolean
      audit: boolean
  denied: string[]
  tool_policies:
    max_concurrent: number
    max_calls_per_task: number
    cost_limit_per_task: string
```

### 8.4 SKILLS/ — Skill Playbooks

Each skill is a Markdown file with structured frontmatter.

```yaml
# Frontmatter schema:
skill:
  id: string
  name: string
  description: string
  trigger: string
  required_tools: string[]
  risk_level: enum
  estimated_duration: duration
```

Body contains step-by-step procedure, format requirements, and limitations.

### 8.5 GUARDRAILS.yaml — Constraints & Safety

```yaml
guardrails:
  schema_version: "1.0"
  input:
    max_length: number
    sanitization: boolean
    jailbreak_detection: boolean
    pii_detection:
      enabled: boolean
      action: enum               # warn | redact | block
    content_filter:
      enabled: boolean
      categories: string[]
  output:
    max_length: number
    pii_check: boolean
    hallucination_check:
      enabled: boolean
      confidence_threshold: number
    format_validation: boolean
    source_citation_required: boolean
  behavioral:
    prohibited_actions: string[]
    required_disclaimers: string[]
    escalation_triggers: string[]
    max_autonomous_steps: number
  compliance:
    framework: string[]
    audit_all_decisions: boolean
    data_classification: enum    # public | internal | confidential | restricted
```

### 8.6 MEMORY.yaml — Memory Configuration

```yaml
memory:
  schema_version: "1.0"
  short_term:
    enabled: boolean
    ttl: duration
    max_entries: number
  episodic:
    enabled: boolean
    confidence_threshold: number
    retrieval_top_k: number
    similarity_threshold: number
    source_required: boolean
  factual:
    enabled: boolean
    confidence_threshold: number
    requires_evidence: boolean
    requires_approval: boolean
    versioned: boolean
  cross_session:
    enabled: boolean
    merge_strategy: enum         # latest | highest_confidence | manual
```

### 8.7 WORKFLOW.yaml — Processes & SOP

```yaml
workflow:
  schema_version: "1.0"
  default_process: enum          # sequential | parallel | adaptive
  sop:
    - id: string
      name: string
      trigger: string
      steps:
        - id: string
          action: string
          tool: string
          on_success: string
          on_failure: string
          timeout: duration
          requires_approval: boolean
      max_duration: duration
      escalation: string
  handoffs:
    - target_agent: string
      conditions: string[]
      context_transfer: enum     # full | summary | minimal
  reporting:
    progress_updates: boolean
    completion_report: boolean
    format: enum                 # structured | narrative | minimal
```

### 8.8 profession-pack.yaml — Pack Manifest

```yaml
schema_version: "1.0"
pack_id: string                  # unique identifier
version: string                  # semver
compatibility:
  framework_min: string
  framework_max: string
  required_tools: string[]
  required_memory: string[]
risk_level: enum                 # low | medium | high | critical
author:
  name: string
  signature: string              # sigstore
  provenance: string             # source URL

# Layer references (file path or inline)
soul:     { extends: string } | { file: string } | { inline object }
role:     { file: string } | { inline object }
tools:    { file: string } | { inline object }
skills:   [ { file: string } | { extends: string } ]
guardrails: { extends: string, override: object } | { file: string }
memory:   { file: string } | { inline object }
workflow: { file: string } | { inline object }

# Evaluation provenance
tested_with:
  - framework: string
    eval_version: string
    eval_score: number
    date: string
```

---

## 9. MUST / SHOULD Summary

| #  | Requirement                                          | Level  |
|----|------------------------------------------------------|--------|
| 1  | Schema Registry for all contracts                    | MUST   |
| 2  | Commands point-to-point, Events pub/sub              | MUST   |
| 3  | RLS + forced tenant_id + no bypass + 3 DB roles      | MUST   |
| 4  | Outbox + Inbox + DLQ pattern                         | MUST   |
| 5  | Memory policy: single TTL source, append-only factual| MUST   |
| 6  | Emergency rollback + freeze + post-factum review     | MUST   |
| 7  | Pack JSON Schema validation in CI                    | MUST   |
| 8  | Trust & Safety as separate domain                    | MUST   |
| 9  | Tool Sandbox with egress/timeout/audit               | MUST   |
| 10 | Clock sync (NTP, <50ms drift)                        | MUST   |
| 11 | Temporal for multi-step workflows                    | SHOULD |
| 12 | Field-level encryption + key rotation                | SHOULD |
| 13 | Shadow-mode evaluation                               | SHOULD |
| 14 | Model tier-based allowlist per tenant/pack            | SHOULD |
| 15 | Capacity limits per tenant/pack/tool                 | SHOULD |
| 16 | Runbook-as-code for SEV1/SEV2                        | SHOULD |
| 17 | Redis logical separation by role                     | SHOULD |
| 18 | SLO-based Kafka migration triggers                   | SHOULD |
| 19 | Consumer-driven contract tests                       | SHOULD |
| 20 | Chaos/resilience tests in staging                    | SHOULD |

---

## 10. Sources & Inspiration

- [OpenClaw](https://openclaw.ai/) — Composable prompt architecture (SOUL.md + AGENTS.md + TOOLS.md + SKILL.md), skill system, multi-agent routing, memory system
- [OpenClaw GitHub](https://github.com/openclaw/openclaw) — 180k+ stars, MIT license
- [OpenClaw Architecture](https://ppaolo.substack.com/p/openclaw-system-architecture-overview) — Technical deep-dive
- CrewAI — Role/goal/backstory agent definition pattern
- OpenAI Agents SDK — Handoffs, guardrails, tracing
- LangGraph — Graph-based stateful workflows, checkpointing
- MetaGPT — SOP-driven multi-agent collaboration
- AutoGen — Conversational multi-agent patterns
- DSPy — Programmatic prompt optimization
- CloudEvents 1.0 — Event envelope standard
