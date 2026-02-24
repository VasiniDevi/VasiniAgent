# Agent-to-Agent Protocol — Design Document

**Date:** 2026-02-24
**Status:** Approved
**Approach:** A+ — Protobuf-First, Transport-Agnostic
**Scope:** Hub-and-spoke orchestrator → specialist delegation with pipeline chaining

---

## 1. Overview

A unified Agent-to-Agent (A2A) communication protocol for the Vasini Agent Framework. The orchestrator (PM Agent) dispatches work to specialist agents, collects results, and chains agents into pipelines — all through a single canonical contract.

### Key Decisions

| Decision | Choice |
|----------|--------|
| Topology | Hub-and-spoke: orchestrator delegates to specialists. No peer-to-peer (evolve to mixed mode later). |
| Runtime | Unified contract, two adapters: dev (Claude Code) + prod (gRPC/events). |
| Schema | Protobuf is the only canonical contract. JSON Schema is generated, never hand-maintained. |
| Context transfer | Adaptive Layered Handoff: required fields always travel, optional context attached by policy. |
| Discovery | Three-layer hybrid: static manifest (identity) + dynamic registry (runtime) + config-driven routing (policy). |
| Chaining | Pipeline templates: orchestrator-owned stage sequences with context propagation. |

### Design Principles

1. **Proto as semantic model** — not "gRPC-only schema." Non-gRPC agents are first-class.
2. **Lowest drift risk** — single source of truth, but adapters and generators can still drift in behavior. Conformance tests catch this.
3. **Orchestrator owns all decisions** — agents never dispatch to each other. Agents are unaware they're part of a pipeline.
4. **Evidence before claims** — every result must include evidence. Auditable even on hard failures.
5. **Transport-agnostic** — gRPC for low-latency, HTTP+JSON for edge/dev, event bus for async. Same envelope.

---

## 2. Proto Definitions — Core Messages

### 2.1 TaskEnvelope (orchestrator → specialist)

```protobuf
syntax = "proto3";

package vasini.agent.v1;

import "google/protobuf/timestamp.proto";
import "google/protobuf/duration.proto";
import "buf/validate/validate.proto";

// ─── TaskEnvelope (orchestrator → specialist) ───────────────────────

message TaskEnvelope {
  ProtocolVersion protocol_version = 1 [(buf.validate.field).required = true];
  Contract        contract         = 2 [(buf.validate.field).required = true];
  TraceContext    trace            = 3 [(buf.validate.field).required = true];
  SafetyContext   safety           = 4 [(buf.validate.field).required = true];
  repeated Ref    refs             = 5 [(buf.validate.field).repeated.min_items = 1];
  Execution       execution        = 6 [(buf.validate.field).required = true];
  ContextIn       context_in       = 7;
  Routing         routing          = 8;

  reserved 9 to 15;
  reserved "envelope_metadata";
}
```

### 2.2 Contract

```protobuf
message Contract {
  string          task_id             = 1 [(buf.validate.field).string.min_len = 1];
  string          title               = 2 [(buf.validate.field).string.min_len = 1];
  string          owner_domain        = 3;  // module/service this touches
  repeated string acceptance_criteria = 4 [(buf.validate.field).repeated.min_items = 1];
  repeated string non_goals           = 5;

  FileManifest    expected_files      = 6;
  TestContract    tests               = 7;
  IOContract      io                  = 8;
  Environment     environment         = 9;

  repeated string definition_of_done  = 10;

  reserved 11 to 15;
  reserved "ownership";
}

message FileManifest {
  repeated string create = 1;
  repeated string modify = 2;
  repeated string delete = 3;
}

message TestContract {
  repeated string tests_to_add = 1;
  repeated string tests_to_run = 2;
}

message IOContract {
  repeated string dependencies         = 1;
  repeated string artifacts             = 2;
  repeated string expected_interfaces   = 3;
  bool            breaking_change       = 4;
}

message Environment {
  string lint_command      = 1;
  string typecheck_command = 2;
  string test_command      = 3;
  string build_command     = 4;
}
```

### 2.3 Execution

```protobuf
message Execution {
  string                    idempotency_key  = 1 [(buf.validate.field).string.min_len = 1];
  string                    dispatch_id      = 2 [(buf.validate.field).string.min_len = 1];
  int32                     attempt_number   = 3;
  google.protobuf.Timestamp deadline         = 4;
  google.protobuf.Duration  timeout          = 5;
  Priority                  priority         = 6 [(buf.validate.field).enum.defined_only = true];
  RiskTier                  risk_tier        = 7 [(buf.validate.field).enum.defined_only = true];
  int32                     patch_size_limit = 8;

  reserved 9 to 14;
  reserved "retry_budget";
}

enum Priority {
  PRIORITY_UNSPECIFIED = 0;
  PRIORITY_LOW         = 1;
  PRIORITY_NORMAL      = 2;
  PRIORITY_HIGH        = 3;
  PRIORITY_CRITICAL    = 4;
}

enum RiskTier {
  RISK_TIER_UNSPECIFIED = 0;
  RISK_TIER_LOW         = 1;
  RISK_TIER_NORMAL      = 2;
  RISK_TIER_CRITICAL    = 3;
}
```

### 2.4 TraceContext

```protobuf
message TraceContext {
  string trace_id       = 1 [(buf.validate.field).string.min_len = 1];
  string span_id        = 2 [(buf.validate.field).string.min_len = 1];
  string parent_span_id = 3;
  string tenant_id      = 4 [(buf.validate.field).string.min_len = 1];
  string agent_id       = 5;

  reserved 6 to 10;
  reserved "pack_version";
}
```

### 2.5 SafetyContext

```protobuf
message SafetyContext {
  repeated string auth_scopes        = 1;
  repeated string prohibited_actions = 2;
  repeated string tool_allowlist     = 3;
  repeated string tool_denylist      = 4;
  int32           max_autonomous_steps = 5;
  SecurityFlags   security_flags     = 6;

  reserved 7 to 10;
}

message SecurityFlags {
  bool touches_auth    = 1;
  bool touches_schema  = 2;
  bool touches_billing = 3;
  bool touches_secrets = 4;
}
```

### 2.6 Ref (versioned, digestable)

```protobuf
message Ref {
  string                    uri_or_locator = 1 [(buf.validate.field).string.min_len = 1];
  string                    version_or_sha = 2;
  string                    digest         = 3;
  google.protobuf.Timestamp fetched_at     = 4;
  RefType                   ref_type       = 5;

  reserved 6 to 8;
}

enum RefType {
  REF_TYPE_UNSPECIFIED  = 0;
  REF_TYPE_FILE         = 1;
  REF_TYPE_COMMIT       = 2;
  REF_TYPE_DB_RECORD    = 3;
  REF_TYPE_URL          = 4;
  REF_TYPE_ARTIFACT     = 5;
}
```

### 2.7 ContextIn (optional, adaptive layered)

```protobuf
message ContextIn {
  string                     shared_context         = 1 [(buf.validate.field).string.max_len = 32768];
  string                     task_delta             = 2 [(buf.validate.field).string.max_len = 16384];
  DecisionMemo               decision_memo          = 3;
  repeated SnippetRef        critical_snippets      = 4;
  repeated string            unresolved_assumptions = 5;

  reserved 6 to 10;
}

message SnippetRef {
  string path        = 1;
  int32  start_line  = 2;
  int32  end_line    = 3;
  string content     = 4 [(buf.validate.field).string.max_len = 4096];
  string description = 5;
}

message DecisionMemo {
  repeated Decision decisions = 1;
}

message Decision {
  string                    decision_id = 1;
  string                    description = 2;
  string                    rationale   = 3;
  string                    source_task = 4;
  google.protobuf.Timestamp decided_at  = 5;
}
```

### 2.8 Routing (auditable dispatch metadata)

```protobuf
message Routing {
  string          selected_pack_id       = 1;
  repeated string candidate_pack_ids     = 2;  // selected_pack_id must be in this list
  string          routing_policy_version = 3;
  string          task_type              = 4;

  reserved 5 to 8;
}
```

### 2.9 AgentResult (specialist → orchestrator)

```protobuf
message AgentResult {
  ProtocolVersion  protocol_version = 1 [(buf.validate.field).required = true];
  ResultStatus     status           = 2 [(buf.validate.field).required = true];
  TraceContext     trace            = 3 [(buf.validate.field).required = true];
  Evidence         evidence         = 4 [(buf.validate.field).required = true];
  ResultTiming     timing           = 5;
  repeated Artifact artifacts       = 6;
  repeated Blocker blockers         = 7;
  ContextOut       context_out      = 8;

  reserved 9 to 14;
}
```

### 2.10 ResultStatus

```protobuf
message ResultStatus {
  Outcome    outcome        = 1 [(buf.validate.field).enum.defined_only = true];
  Confidence confidence     = 2 [(buf.validate.field).enum.defined_only = true];
  string     summary        = 3;
  string     failure_code   = 4;  // stable taxonomy key (e.g. "TEST_SUITE_FAILED")
  string     failure_reason = 5;  // human-readable explanation

  reserved 6 to 10;
}

enum Outcome {
  OUTCOME_UNSPECIFIED             = 0;
  OUTCOME_SUCCESS                 = 1;
  OUTCOME_PARTIAL                 = 2;
  OUTCOME_RETRYABLE_FAILURE       = 3;
  OUTCOME_NON_RETRYABLE_FAILURE   = 4;
  OUTCOME_POLICY_BLOCKED          = 5;
}

enum Confidence {
  CONFIDENCE_UNSPECIFIED = 0;
  CONFIDENCE_CONFIDENT   = 1;
  CONFIDENCE_UNCERTAIN   = 2;
  CONFIDENCE_BLOCKED     = 3;
}
```

### 2.11 ResultTiming

```protobuf
message ResultTiming {
  google.protobuf.Timestamp started_at  = 1;
  google.protobuf.Timestamp finished_at = 2;
  google.protobuf.Duration  duration    = 3;
}
```

### 2.12 Evidence (mutually exclusive modes)

```protobuf
message Evidence {
  oneof evidence_payload {
    EvidenceItems items            = 1;
    string        none_with_reason = 2;
  }
}

message EvidenceItems {
  repeated EvidenceItem items = 1 [(buf.validate.field).repeated.min_items = 1];
}

message EvidenceItem {
  EvidenceType type    = 1;
  string       command = 2;
  string       output  = 3 [(buf.validate.field).string.max_len = 65536];
  bool         passed  = 4;

  reserved 5 to 8;
}

enum EvidenceType {
  EVIDENCE_TYPE_UNSPECIFIED = 0;
  EVIDENCE_TYPE_TEST        = 1;
  EVIDENCE_TYPE_LINT        = 2;
  EVIDENCE_TYPE_TYPECHECK   = 3;
  EVIDENCE_TYPE_BUILD       = 4;
  EVIDENCE_TYPE_SECURITY    = 5;
  EVIDENCE_TYPE_MANUAL      = 6;
}
```

### 2.13 Artifact, Blocker, ContextOut

```protobuf
message Artifact {
  string         path   = 1;
  ArtifactAction action = 2;
  string         digest = 3;

  reserved 4 to 6;
}

enum ArtifactAction {
  ARTIFACT_ACTION_UNSPECIFIED = 0;
  ARTIFACT_ACTION_CREATED     = 1;
  ARTIFACT_ACTION_MODIFIED    = 2;
  ARTIFACT_ACTION_DELETED     = 3;
}

message Blocker {
  string      description          = 1;
  BlockerType blocker_type         = 2;
  string      suggested_resolution = 3;

  reserved 4 to 6;
}

enum BlockerType {
  BLOCKER_TYPE_UNSPECIFIED            = 0;
  BLOCKER_TYPE_AMBIGUOUS_REQUIREMENT  = 1;
  BLOCKER_TYPE_DEPENDENCY_MISSING     = 2;
  BLOCKER_TYPE_TOOL_FAILURE           = 3;
  BLOCKER_TYPE_PERMISSION_DENIED      = 4;
  BLOCKER_TYPE_TIMEOUT                = 5;
}

message ContextOut {
  repeated Decision decisions_made   = 1;
  repeated string   risks_identified = 2;
  repeated string   assumptions_made = 3;
  string            rollback_notes   = 4;

  reserved 5 to 8;
}
```

### 2.14 HandoffPolicy (orchestrator config, per-dispatch)

```protobuf
message HandoffPolicy {
  ContextLevel     context_level = 1;
  EscalationPolicy escalation    = 2;
  RetryPolicy      retry         = 3;  // single source of truth for retry config
  FreshnessPolicy  freshness     = 4;

  reserved 5 to 8;
}

enum ContextLevel {
  CONTEXT_LEVEL_UNSPECIFIED = 0;
  CONTEXT_LEVEL_MINIMAL     = 1;
  CONTEXT_LEVEL_LAYERED     = 2;
  CONTEXT_LEVEL_RICH        = 3;
}

message EscalationPolicy {
  repeated string auto_escalate_on_security_flag = 1;
  bool            escalate_on_policy_blocked     = 2;

  reserved 3 to 6;
}

message RetryPolicy {
  int32                    max_attempts       = 1;
  google.protobuf.Duration initial_backoff    = 2;
  double                   backoff_multiplier = 3;
  google.protobuf.Duration max_backoff        = 4;

  reserved 5 to 8;
}

message FreshnessPolicy {
  google.protobuf.Duration max_ref_staleness = 1;
  bool                     require_digest    = 2;

  reserved 3 to 6;
}
```

### 2.15 ProtocolVersion

```protobuf
message ProtocolVersion {
  string schema_version            = 1 [(buf.validate.field).string.min_len = 1];
  string policy_version            = 2;
  string capability_schema_version = 3;
  string pack_version              = 4;
  string min_orchestrator_version  = 5;

  reserved 6 to 10;
}
```

---

## 3. Discovery & Dispatch Flow

### 3.1 Three-Layer Discovery Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 3: ROUTING POLICY                   │
│  Human-owned rules: task_type → allowed pack_ids + tier     │
│  Config-driven, version-controlled, auditable               │
│  "Which agents MAY handle this task type?"                  │
├─────────────────────────────────────────────────────────────┤
│                    Layer 2: DYNAMIC REGISTRY                 │
│  Runtime state: health, capacity, latency, tool availability│
│  Heartbeat-driven, auto-expires stale entries               │
│  "Which allowed agents are ABLE to handle it right now?"    │
├─────────────────────────────────────────────────────────────┤
│                    Layer 1: STATIC MANIFEST                  │
│  Canonical identity: pack_id, interface version, safety tier│
│  From profession-pack.yaml, immutable per version           │
│  "What agents EXIST and what are their contracts?"          │
└─────────────────────────────────────────────────────────────┘
```

**Layer 1 — Static Manifest** (bootstrap, source of truth for identity)

```protobuf
message AgentManifest {
  string          pack_id                    = 1 [(buf.validate.field).string.min_len = 1];
  string          pack_version               = 2 [(buf.validate.field).string.min_len = 1];
  string          capability_schema_version  = 3;
  string          min_orchestrator_version   = 4;
  RiskTier        safety_tier                = 5 [(buf.validate.field).enum.defined_only = true];
  repeated string supported_task_types       = 6;
  repeated string provided_tools             = 7;
  repeated string required_tools             = 8;
  repeated string owner_domains              = 9;
  InterfaceContract interface                = 10;

  reserved 11 to 15;
}

message InterfaceContract {
  repeated string supported_schema_versions = 1;  // semver list this agent speaks
  repeated string accepted_risk_tiers       = 2;
  int32           max_concurrent_tasks      = 3;
  google.protobuf.Duration max_task_duration = 4;

  reserved 5 to 8;
}
```

Populated from `profession-pack.yaml`. Immutable per version. Stored in Pack Registry.

Registration-time validation (Layer 2 admission): static compatibility only — `capability_schema_version`, `min_orchestrator_version`, manifest schema validity. Task-specific checks (risk tier, tools, etc.) happen at dispatch time only.

---

**Layer 2 — Dynamic Registry** (runtime state)

```protobuf
message AgentHeartbeat {
  string                    pack_id      = 1 [(buf.validate.field).string.min_len = 1];
  string                    instance_id  = 2 [(buf.validate.field).string.min_len = 1];
  AgentHealth               health       = 3;
  AgentCapacity             capacity     = 4;
  google.protobuf.Timestamp heartbeat_at = 5;
  google.protobuf.Duration  lease_ttl    = 6;

  reserved 7 to 10;
}

message AgentHealth {
  HealthStatus              status         = 1;
  double                    error_rate_1m  = 2;
  google.protobuf.Duration  avg_latency_1m = 3;
  repeated string           degraded_tools = 4;
  int32                     consecutive_invalid_results = 5;

  reserved 6 to 10;
}

enum HealthStatus {
  HEALTH_STATUS_UNSPECIFIED = 0;
  HEALTH_STATUS_HEALTHY     = 1;
  HEALTH_STATUS_DEGRADED    = 2;
  HEALTH_STATUS_UNHEALTHY   = 3;
  HEALTH_STATUS_QUARANTINED = 4;
}

message AgentCapacity {
  int32 active_tasks = 1;
  int32 max_tasks    = 2;
  int32 queued_tasks = 3;

  reserved 4 to 6;
}
```

Dev adapter: single instance with synthetic health/capacity model — reflects tool failures and timeouts as `DEGRADED`, capacity = 1 (serial sub-agent execution).

---

**Layer 3 — Routing Policy** (human-owned config)

```yaml
# config/routing-policy.yaml (version-controlled)
routing_policy:
  version: "1.0.0"

  routes:
    - task_type: "feature-implementation"
      allowed_pack_ids: ["senior-python-dev", "senior-ts-dev"]
      preferred_pack_id: "senior-python-dev"
      min_risk_tier: RISK_TIER_NORMAL
      fallback_pack_id: "generalist-dev"

    - task_type: "code-review"
      allowed_pack_ids: ["qa-engineer", "senior-python-dev"]
      preferred_pack_id: "qa-engineer"
      min_risk_tier: RISK_TIER_LOW
      fallback_pack_id: null  # escalate if unavailable

    - task_type: "security-review"
      allowed_pack_ids: ["security-reviewer"]
      preferred_pack_id: "security-reviewer"
      min_risk_tier: RISK_TIER_CRITICAL
      fallback_pack_id: null  # always escalate

  admission:
    max_global_queue_depth: 50
    max_per_pack_concurrent: 3
    circuit_breaker:
      error_threshold: 5
      window: "60s"
      half_open_after: "120s"

  defaults:
    fallback_pack_id: "generalist-dev"
    max_candidate_agents: 3
    require_healthy: true
```

---

### 3.2 Dispatch Flow

```
Orchestrator receives next task from queue
            │
            ▼
┌──────────────────────────┐
│ 1. ADMISSION CONTROL     │  Check global queue depth
│                          │  Check per-pack concurrency limit
│                          │  Check circuit breaker state for task_type
│                          │  If breaker OPEN: reject + escalate
└───────────┬──────────────┘
            ▼
┌──────────────────────────┐
│ 2. MATCH                 │  Routing policy: task_type → route
│    task_type → route     │  If no route: ESCALATE to human
└───────────┬──────────────┘
            ▼
┌──────────────────────────┐
│ 3. FILTER + RANK         │
│                          │  Static filter:
│                          │    allowed_pack_ids from route
│                          │    ∩ semver_satisfies(
│                          │        envelope.schema_version,
│                          │        manifest.supported_schema_versions)
│                          │    ∩ manifest.min_orchestrator_version
│                          │        <= orchestrator.version
│                          │    ∩ task.risk_tier ∈
│                          │        manifest.accepted_risk_tiers
│                          │    ∩ contract.required_tools ⊆
│                          │        (manifest.provided_tools
│                          │         ∪ heartbeat.available_tools
│                          │         − heartbeat.degraded_tools)
│                          │
│                          │  Dynamic rank:
│                          │    Exclude UNHEALTHY + QUARANTINED
│                          │    HEALTHY > DEGRADED
│                          │    Lowest active/max ratio
│                          │    Lowest avg_latency_1m
│                          │    preferred_pack_id wins ties
│                          │
│                          │  Select top-ranked agent
│                          │  Record: selected, all candidates,
│                          │          routing_policy_version
│                          │
│                          │  If none pass: try fallback_pack_id
│                          │    (fallback MUST pass same filter)
│                          │  If fallback fails: ESCALATE
└───────────┬──────────────┘
            ▼
┌──────────────────────────┐
│ 4. CONTEXT ASSEMBLY      │  HandoffPolicy.context_level decides:
│    Apply HandoffPolicy   │  MINIMAL: contract + trace + safety + refs
│                          │  LAYERED: + decision_memo, snippets
│                          │  RICH: + shared_context, task_delta,
│                          │         assumptions
│                          │
│    Freshness check:      │  For each ref:
│                          │   refresh succeeds → continue
│                          │   refresh fails + strict policy
│                          │     (require_digest=true OR
│                          │      staleness > hard threshold)
│                          │     → BLOCK, escalate
│                          │   refresh fails + non-strict
│                          │     → continue with degraded flag
└───────────┬──────────────┘
            ▼
┌──────────────────────────┐
│ 5. DISPATCH              │  Build TaskEnvelope
│    Assign dispatch_id    │  Set attempt_number
│    Set idempotency_key   │  Log: decision + policy snapshot
│    Send via adapter      │
│                          │  Dev:  Task tool → sub-agent (JSON)
│                          │  Prod: AgentService.RunAgent (proto)
│                          │  Async: envelope → event bus
└───────────┬──────────────┘
            ▼
┌──────────────────────────┐
│ 6. AWAIT + MONITOR       │  Track: deadline, timeout
│                          │  Prod: heartbeat lease enforcement
│                          │  Dev: await sub-agent completion
│                          │
│    On timeout:           │  Emit explicit CancelAgent signal
│                          │  Require idempotent handling
│                          │  Return RETRYABLE_FAILURE
│                          │  Re-enter dispatch: attempt_number + 1
└───────────┬──────────────┘
            ▼
┌──────────────────────────┐
│ 7. RECEIVE + VALIDATE    │  Validate ALL of:
│                          │    protocol_version compatible
│                          │    trace_id matches envelope
│                          │    dispatch_id matches envelope
│                          │    attempt_number matches
│                          │    schema validates
│                          │
│    On valid result:      │  Log full result + timing
│                          │  Route to Review Gate (PM flow)
│                          │
│    On invalid result:    │  First occurrence from instance:
│                          │    RETRYABLE_FAILURE, increment
│                          │    consecutive_invalid_results
│                          │  Repeated (≥3) from same instance:
│                          │    QUARANTINE instance
│                          │    Reroute to next candidate or
│                          │    escalate
└──────────────────────────┘
```

**Failure paths:**

| Step | Failure | Action |
|------|---------|--------|
| 1. ADMISSION | Queue full / breaker OPEN | Reject + escalate to human |
| 2. MATCH | No route for task_type | Escalate to human |
| 3. FILTER+RANK | No compatible agents | Try fallback (must pass same filter). If none: escalate |
| 4. CONTEXT | Stale refs, strict policy | Block + escalate |
| 4. CONTEXT | Stale refs, non-strict | Continue with degraded flag in envelope |
| 5. DISPATCH | Transport failure | Retry with backoff per RetryPolicy |
| 6. AWAIT | Timeout / heartbeat loss | Cancel + RETRYABLE_FAILURE + re-enter dispatch |
| 7. RECEIVE | Invalid result (first) | RETRYABLE_FAILURE, increment invalid count |
| 7. RECEIVE | Invalid result (repeated ≥3) | QUARANTINE instance, reroute or escalate |

---

### 3.3 Compatibility Gate (Dispatch-Time)

```
Agent compatible for this task IF:
  semver_satisfies(
    envelope.protocol_version.schema_version,
    manifest.interface.supported_schema_versions
  )
  AND manifest.min_orchestrator_version <= orchestrator.version
  AND task.execution.risk_tier ∈ manifest.interface.accepted_risk_tiers
  AND contract.required_tools ⊆
      (manifest.provided_tools ∪ heartbeat.available_tools
       − heartbeat.degraded_tools)
  AND agent.health_status ∉ {UNHEALTHY, QUARANTINED}
  AND per_pack_concurrent < admission.max_per_pack_concurrent
  AND circuit_breaker.state ≠ OPEN for this pack_id
```

`contract.required_tools` is sourced from `Contract.environment` (lint, typecheck, test, build commands) plus `IOContract.dependencies`. Agents declare their tool coverage in `AgentManifest.provided_tools`.

---

### 3.4 Dev vs Prod Adapter Mapping

| Concern | Dev Adapter (Claude Code) | Prod Adapter (gRPC/Events) |
|---------|--------------------------|---------------------------|
| Discovery L1 | Read pack manifests from `packs/` directory | Query Pack Registry service |
| Discovery L2 | Single instance, synthetic health model (reflects tool failures/timeouts as DEGRADED) | Heartbeat service, Redis-backed |
| Discovery L3 | Routing policy YAML loaded at session start | Routing policy from Control Plane |
| Admission | Simplified: serial execution, no circuit breaker | Full: queue depth, concurrency, circuit breaker |
| Dispatch | `Task` tool → sub-agent with JSON envelope | `AgentService.RunAgent` with proto envelope |
| Monitor | Await sub-agent return, timeout only | Heartbeat lease + timeout + cancel signal |
| Cancel | Sub-agent timeout → discard result | `CancelAgent` RPC + idempotent retry |
| Result | Parse sub-agent output → AgentResult JSON, basic validation | Full validation + quarantine logic |

---

## 4. Pipeline Chaining & Lifecycle

### 4.1 Pipeline Model

A pipeline is an orchestrator-owned sequence of dispatch stages. Each stage is a `TaskEnvelope` dispatch. The orchestrator controls all transitions — agents never dispatch to each other directly.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Pipeline (orchestrator-owned)                │
│                                                                 │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌────────┐ │
│  │ Stage 1  │────▶│ Stage 2  │────▶│ Stage 3  │────▶│Stage N │ │
│  │ analyst  │     │implement │     │ reviewer │     │verifier│ │
│  └──────────┘     └──────────┘     └──────────┘     └────────┘ │
│       │                │                │                │      │
│   AgentResult      AgentResult      AgentResult      AgentResult│
│       │                │                │                │      │
│       ▼                ▼                ▼                ▼      │
│  Orchestrator evaluates each result, decides:                   │
│    ADVANCE → next stage                                         │
│    RETRY   → same stage, attempt_number + 1                     │
│    REJECT  → earlier stage with feedback                        │
│    ABORT   → cancel pipeline, escalate                          │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.2 Proto Definitions

```protobuf
message Pipeline {
  string              pipeline_id     = 1 [(buf.validate.field).string.min_len = 1];
  string              pipeline_name   = 2;
  string              source_task_id  = 3;
  PipelineStatus      status          = 4;
  repeated Stage      stages          = 5 [(buf.validate.field).repeated.min_items = 1];
  TraceContext        trace           = 6 [(buf.validate.field).required = true];
  PipelinePolicy      policy          = 7;

  google.protobuf.Timestamp created_at  = 8;
  google.protobuf.Timestamp updated_at  = 9;

  reserved 10 to 15;
}

enum PipelineStatus {
  PIPELINE_STATUS_UNSPECIFIED = 0;
  PIPELINE_STATUS_PENDING     = 1;
  PIPELINE_STATUS_RUNNING     = 2;
  PIPELINE_STATUS_PAUSED      = 3;
  PIPELINE_STATUS_COMPLETED   = 4;
  PIPELINE_STATUS_FAILED      = 5;
  PIPELINE_STATUS_ABORTED     = 6;
}

message Stage {
  string              stage_id         = 1 [(buf.validate.field).string.min_len = 1];
  int32               stage_order      = 2;
  string              stage_name       = 3;
  string              task_type        = 4;
  StageStatus         status           = 5;
  StageConfig         config           = 6;

  string              dispatch_id      = 7;
  string              assigned_pack_id = 8;
  int32               attempt_number   = 9;

  AgentResult         result           = 10;

  reserved 11 to 15;
}

enum StageStatus {
  STAGE_STATUS_UNSPECIFIED = 0;
  STAGE_STATUS_PENDING     = 1;
  STAGE_STATUS_READY       = 2;
  STAGE_STATUS_DISPATCHED  = 3;
  STAGE_STATUS_COMPLETED   = 4;
  STAGE_STATUS_FAILED      = 5;
  STAGE_STATUS_SKIPPED     = 6;
  STAGE_STATUS_REJECTED    = 7;
}

message StageConfig {
  Contract            contract_template   = 1;
  HandoffPolicy       handoff_policy      = 2;
  bool                required            = 3;
  repeated string     depends_on_stages   = 4;
  ContextPropagation  context_propagation = 5;

  reserved 6 to 10;
}

message ContextPropagation {
  ContextPropagationMode mode            = 1;
  repeated string carry_fields           = 2;
  bool            carry_artifacts        = 3;
  bool            carry_decisions        = 4;
  bool            carry_risks            = 5;

  reserved 6 to 8;
}

enum ContextPropagationMode {
  CONTEXT_PROPAGATION_MODE_UNSPECIFIED = 0;
  CONTEXT_PROPAGATION_MODE_NONE        = 1;
  CONTEXT_PROPAGATION_MODE_PREVIOUS    = 2;
  CONTEXT_PROPAGATION_MODE_CUMULATIVE  = 3;
}

message PipelinePolicy {
  int32                    max_total_retries  = 1;
  int32                    max_rejections     = 2;
  google.protobuf.Duration pipeline_deadline  = 3;
  FailureStrategy          failure_strategy   = 4;
  bool                     require_all_stages = 5;

  reserved 6 to 10;
}

enum FailureStrategy {
  FAILURE_STRATEGY_UNSPECIFIED  = 0;
  FAILURE_STRATEGY_FAIL_FAST   = 1;
  FAILURE_STRATEGY_SKIP_FAILED = 2;
  FAILURE_STRATEGY_PAUSE       = 3;
}
```

---

### 4.3 Pipeline Execution Flow

```
Orchestrator creates Pipeline from plan task
            │
            ▼
┌──────────────────────────────┐
│ 1. INITIALIZE                │
│    Build Stage list from     │  Resolve dependencies (topological sort)
│    pipeline template         │  Set pipeline RUNNING
│    Set stage 0 → READY       │  Start pipeline timer
│    All others → PENDING      │
└───────────┬──────────────────┘
            │
    ┌───────▼───────┐
    │ 2. STAGE LOOP │◀──────────────────────────────────┐
    └───────┬───────┘                                    │
            ▼                                            │
┌──────────────────────────────┐                         │
│ 3. BUILD ENVELOPE            │                         │
│                              │                         │
│    Contract:                 │                         │
│      stage.contract_template │                         │
│      + task-specific fields  │                         │
│      + required_tools from   │                         │
│        stage task_type       │                         │
│                              │                         │
│    Context assembly:         │                         │
│      propagation.mode:       │                         │
│        NONE → clean slate    │                         │
│        PREVIOUS → prior      │                         │
│          stage context_out   │                         │
│        CUMULATIVE → merged   │                         │
│          context_out from    │                         │
│          all completed       │                         │
│          stages              │                         │
│                              │                         │
│    Refs:                     │                         │
│      Prior artifacts as refs │                         │
│      (if carry_artifacts)    │                         │
│                              │                         │
│    Decisions:                │                         │
│      Accumulated memo        │                         │
│      (if carry_decisions)    │                         │
└───────────┬──────────────────┘                         │
            ▼                                            │
┌──────────────────────────────┐                         │
│ 4. DISPATCH                  │                         │
│    (Section 3 flow:          │                         │
│     admission → match →      │                         │
│     filter+rank → context →  │                         │
│     dispatch → await →       │                         │
│     receive+validate)        │                         │
│                              │                         │
│    Stage → DISPATCHED        │                         │
└───────────┬──────────────────┘                         │
            ▼                                            │
┌──────────────────────────────┐                         │
│ 5. EVALUATE RESULT           │                         │
│                              │                         │
│    SUCCESS → ADVANCE         │─── next stage READY ───▶│
│    PARTIAL → review decides  │─── ADVANCE or RETRY ───▶│
│    RETRYABLE_FAILURE         │                         │
│      within budget → RETRY   │─── same stage ─────────▶│
│      exhausted → fail strat  │                         │
│    NON_RETRYABLE → fail strat│                         │
│    POLICY_BLOCKED → PAUSE    │                         │
└───────────┬──────────────────┘                         │
            ▼                                            │
┌──────────────────────────────┐                         │
│ 6. REVIEW GATE               │                         │
│    (existing PM Agent flow)  │                         │
│                              │                         │
│    PASS → ADVANCE            │─── next stage READY ───▶│
│    FAIL (fixable) →          │                         │
│      REJECT to target stage  │─── rewind + retry ─────▶│
│    FAIL (unfixable) →        │                         │
│      failure_strategy        │                         │
└──────────────────────────────┘                         │
                                                         │
┌──────────────────────────────┐                         │
│ 7. PIPELINE COMPLETE         │◀── (no more stages) ───┘
│    Aggregate all artifacts,  │
│    decisions, risks, timing  │
│    → Route to PM commit flow │
└──────────────────────────────┘
```

---

### 4.4 Pipeline Templates

Defined in routing policy config. The orchestrator instantiates these when a plan task requires multi-stage execution.

```yaml
# config/pipeline-templates.yaml (version-controlled)
pipeline_templates:
  version: "1.0.0"

  templates:
    - template_id: "implement-and-review"
      name: "Standard Implementation"
      description: "Implement feature, review code, verify tests"
      stages:
        - stage_id: "implement"
          task_type: "feature-implementation"
          required: true
          context_propagation:
            mode: NONE
          handoff_policy:
            context_level: LAYERED
            retry: { max_attempts: 2 }
            freshness: { max_ref_staleness: "5m" }

        - stage_id: "review"
          task_type: "code-review"
          required: true
          depends_on_stages: ["implement"]
          context_propagation:
            mode: PREVIOUS
            carry_artifacts: true
            carry_decisions: true
            carry_risks: true
          handoff_policy:
            context_level: RICH
            retry: { max_attempts: 1 }

        - stage_id: "verify"
          task_type: "verification"
          required: true
          depends_on_stages: ["review"]
          context_propagation:
            mode: CUMULATIVE
            carry_artifacts: true
            carry_decisions: true
            carry_risks: true
          handoff_policy:
            context_level: LAYERED
            retry: { max_attempts: 1 }

      policy:
        max_total_retries: 4
        max_rejections: 2
        pipeline_deadline: "30m"
        failure_strategy: PAUSE

    - template_id: "critical-with-security"
      name: "Critical Implementation with Security Review"
      stages:
        - stage_id: "implement"
          task_type: "feature-implementation"
          required: true
          context_propagation: { mode: NONE }

        - stage_id: "security-review"
          task_type: "security-review"
          required: true
          depends_on_stages: ["implement"]
          context_propagation:
            mode: PREVIOUS
            carry_artifacts: true

        - stage_id: "review"
          task_type: "code-review"
          required: true
          depends_on_stages: ["implement"]
          context_propagation:
            mode: PREVIOUS
            carry_artifacts: true
            carry_decisions: true

        - stage_id: "verify"
          task_type: "verification"
          required: true
          depends_on_stages: ["security-review", "review"]
          context_propagation:
            mode: CUMULATIVE
            carry_artifacts: true
            carry_decisions: true
            carry_risks: true

      policy:
        max_total_retries: 4
        max_rejections: 2
        pipeline_deadline: "60m"
        failure_strategy: PAUSE
        require_all_stages: true
```

Note: `critical-with-security` has a diamond dependency — `security-review` and `review` run after `implement` and can execute in parallel if both agents are available and routing policy allows. `verify` waits for both.

---

### 4.5 Lifecycle State Machines

**Pipeline lifecycle:**

```
PENDING → RUNNING → COMPLETED
              ├───→ PAUSED → RUNNING  (human unblocks)
              │        └───→ ABORTED  (human cancels)
              └───→ FAILED            (failure_strategy = FAIL_FAST)
```

**Stage lifecycle:**

```
PENDING → READY → DISPATCHED → COMPLETED
                       ├─────→ DISPATCHED  (RETRY: same stage, new attempt)
                       ├─────→ READY       (REJECT: rewind to this or earlier stage)
                       ├─────→ FAILED      (exhausted retries)
                       └─────→ SKIPPED     (non-required + SKIP_FAILED strategy)
```

**Invariants:**
- Pipeline COMPLETED only when all required stages are COMPLETED and all non-required stages are COMPLETED or SKIPPED
- Pipeline RUNNING requires at least one stage READY or DISPATCHED
- Stage READY requires all `depends_on_stages` to be COMPLETED
- REJECT resets target stage to READY with `attempt_number + 1` and includes review failure evidence in `context_in`
- Total retries across all stages tracked against `pipeline_policy.max_total_retries`
- Total rejections tracked against `pipeline_policy.max_rejections`
- Pipeline timer tracked against `pipeline_policy.pipeline_deadline` — on expiry, PAUSE + escalate

---

### 4.6 Rejection (Rewind) Semantics

When the review gate rejects a stage result:

```
Review gate rejects Stage N result
            │
            ▼
    Determine rewind target:
      - Default: rewind to Stage N (same stage re-executes)
      - If root cause is in earlier stage: rewind to Stage M (M < N)
      - Orchestrator decides based on review evidence
            │
            ▼
    Target stage → REJECTED → READY
    All stages after target → PENDING (reset)
    Target stage attempt_number += 1
            │
            ▼
    Build new context_in for target stage:
      - Original contract (unchanged)
      - Review failure evidence (what failed, why)
      - Prior attempt's context_out (what was tried)
      - Specific fix instructions from review gate
            │
            ▼
    Re-enter Stage Loop at target stage
```

---

### 4.7 Dev vs Prod Pipeline Differences

| Concern | Dev Adapter | Prod Adapter |
|---------|-------------|--------------|
| Parallelism | Serial only — one stage at a time, diamond deps run sequentially | Parallel dispatch for independent stages |
| Templates | Loaded from `config/pipeline-templates.yaml` | Loaded from Control Plane |
| Timer | Soft deadline — warn, don't enforce | Hard deadline — PAUSE on expiry |
| Rejection | Orchestrator (PM skill) decides rewind target | Same, with richer review evidence |
| State persistence | In-memory (session-scoped) | Database-backed (survives restarts) |

---

## 5. Observability & Audit

### 5.1 Trace Hierarchy

Every agent interaction produces a trace tree rooted at the pipeline level.

```
Pipeline Trace (pipeline_id as root span)
│
├── Stage 1: "implement" (stage span)
│   ├── Dispatch Decision (child span)
│   │   ├── admission_check
│   │   ├── route_match
│   │   ├── filter_rank (candidates, selected, policy_version)
│   │   └── context_assembly (freshness checks, propagation mode)
│   │
│   ├── Agent Execution (child span, agent's span_id)
│   │   ├── tool calls (agent-internal)
│   │   └── evidence collection
│   │
│   ├── Result Validation (child span)
│   │   └── schema_check, trace_match, dispatch_match
│   │
│   └── Review Gate (child span)
│       ├── minimum_gate_checks
│       └── tier_review
│
├── Stage 2: "review" (stage span)
│   └── ... same structure ...
│
└── Pipeline Complete (final span)
    └── aggregate_timing, artifact_summary, risk_summary
```

**Correlation fields carried on every span:**

| Field | Source | Purpose |
|-------|--------|---------|
| `trace_id` | Pipeline root | Links all spans |
| `span_id` | Per-operation | Unique per span |
| `parent_span_id` | Caller's span_id | Builds tree |
| `tenant_id` | Request origin | Tenant isolation |
| `agent_id` | Assigned agent instance | Which agent ran |
| `pipeline_id` | Pipeline message | Which pipeline |
| `stage_id` | Stage message | Which stage |
| `dispatch_id` | Execution message | Which dispatch attempt |
| `attempt_number` | Execution message | Retry tracking |

**Sampling policy:** Traces MAY be sampled (head-based or tail-based). Audit events are NEVER sampled — 100% capture, no exceptions.

---

### 5.2 Audit Log

```protobuf
message AuditEntry {
  string                    audit_id         = 1 [(buf.validate.field).string.min_len = 1];
  AuditEventType            event_type       = 2 [(buf.validate.field).enum.defined_only = true];
  google.protobuf.Timestamp timestamp        = 3;
  ProtocolVersion           protocol_version = 4;

  // Correlation (top-level for queryability)
  string                    trace_id       = 5;
  string                    tenant_id      = 6;
  string                    pipeline_id    = 7;
  string                    stage_id       = 8;
  string                    dispatch_id    = 9;
  int32                     attempt_number = 10;
  string                    pack_id        = 11;

  // Actor (structured)
  AuditActor                actor          = 12;

  // Decision
  string                    action         = 13;
  string                    rationale      = 14;  // MUST be redacted of secrets

  // Snapshot
  AuditSnapshot             snapshot       = 15;

  reserved 16 to 22;
}

message AuditActor {
  ActorType type = 1;
  string    id   = 2;

  reserved 3 to 4;
}

enum ActorType {
  ACTOR_TYPE_UNSPECIFIED  = 0;
  ACTOR_TYPE_ORCHESTRATOR = 1;
  ACTOR_TYPE_AGENT        = 2;
  ACTOR_TYPE_HUMAN        = 3;
  ACTOR_TYPE_SYSTEM       = 4;
}

enum AuditEventType {
  AUDIT_EVENT_TYPE_UNSPECIFIED         = 0;

  // Pipeline lifecycle
  AUDIT_EVENT_TYPE_PIPELINE_CREATED    = 1;
  AUDIT_EVENT_TYPE_PIPELINE_COMPLETED  = 2;
  AUDIT_EVENT_TYPE_PIPELINE_FAILED     = 3;
  AUDIT_EVENT_TYPE_PIPELINE_PAUSED     = 4;
  AUDIT_EVENT_TYPE_PIPELINE_RESUMED    = 5;
  AUDIT_EVENT_TYPE_PIPELINE_ABORTED    = 6;

  // Dispatch lifecycle
  AUDIT_EVENT_TYPE_DISPATCH_DECISION   = 10;
  AUDIT_EVENT_TYPE_DISPATCH_SENT       = 11;
  AUDIT_EVENT_TYPE_DISPATCH_TIMEOUT    = 12;
  AUDIT_EVENT_TYPE_DISPATCH_CANCELLED  = 13;

  // Result lifecycle
  AUDIT_EVENT_TYPE_RESULT_RECEIVED     = 20;
  AUDIT_EVENT_TYPE_RESULT_VALIDATED    = 21;
  AUDIT_EVENT_TYPE_RESULT_INVALID      = 22;

  // Review gate
  AUDIT_EVENT_TYPE_GATE_PASSED         = 30;
  AUDIT_EVENT_TYPE_GATE_FAILED         = 31;
  AUDIT_EVENT_TYPE_GATE_REJECTED       = 32;

  // Agent health
  AUDIT_EVENT_TYPE_AGENT_QUARANTINED   = 40;
  AUDIT_EVENT_TYPE_AGENT_RESTORED      = 41;

  // Escalation
  AUDIT_EVENT_TYPE_ESCALATION          = 50;
  AUDIT_EVENT_TYPE_ESCALATION_RESOLVED = 51;

  reserved 60 to 100;
}

message AuditSnapshot {
  oneof snapshot_payload {
    DispatchSnapshot   dispatch   = 1;
    ResultSnapshot     result     = 2;
    GateSnapshot       gate       = 3;
    EscalationSnapshot escalation = 4;
  }
}

message DispatchSnapshot {
  string          selected_pack_id       = 1;
  repeated string candidate_pack_ids     = 2;
  string          routing_policy_version = 3;
  string          rejection_reasons      = 4;
  ContextLevel    context_level_applied  = 5;
  int32           attempt_number         = 6;
  repeated RefFreshnessCheck ref_freshness = 7;

  reserved 8 to 10;
}

message RefFreshnessCheck {
  string uri_or_locator            = 1;
  bool   was_stale                 = 2;
  bool   refresh_succeeded         = 3;
  bool   dispatched_with_degraded  = 4;
}

message ResultSnapshot {
  Outcome         outcome                 = 1;
  Confidence      confidence              = 2;
  string          failure_code            = 3;
  int32           artifacts_count         = 4;
  int32           evidence_count          = 5;
  int32           blockers_count          = 6;
  ResultTiming    timing                  = 7;
  bool            validation_passed       = 8;
  string          validation_error        = 9;
  string          schema_version_received = 10;
  string          schema_version_expected = 11;

  reserved 12 to 15;
}

message GateSnapshot {
  repeated GateCheck checks              = 1;
  string             tier                = 2;
  bool               passed              = 3;
  string             reject_reason       = 4;
  string             rewind_target_stage = 5;
}

message GateCheck {
  string gate_name = 1;
  bool   passed    = 2;
  string evidence  = 3;
}

message EscalationSnapshot {
  string          problem      = 1;
  string          impact       = 2;
  repeated string options      = 3;
  string          recommended  = 4;
  bool            blocking     = 5;
  string          resolution   = 6;
  string          resolved_by  = 7;
}
```

**Audit immutability enforcement (production):**

```sql
CREATE TABLE audit_log (
    audit_id       TEXT PRIMARY KEY,
    event_type     TEXT NOT NULL,
    timestamp_utc  TIMESTAMPTZ NOT NULL DEFAULT now(),
    tenant_id      TEXT NOT NULL,
    payload        JSONB NOT NULL
);

-- No UPDATE/DELETE for application role
REVOKE UPDATE, DELETE ON audit_log FROM app_role;
GRANT INSERT, SELECT ON audit_log TO app_role;

-- No DELETE for migration role either
REVOKE DELETE ON audit_log FROM migration_role;

-- Trigger guard (defense in depth)
CREATE OR REPLACE FUNCTION prevent_audit_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: UPDATE/DELETE prohibited';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_audit_update
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

-- RLS for tenant isolation
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON audit_log
    USING (tenant_id = current_setting('app.tenant_id', true));
```

---

### 5.3 Redaction Policy

Sensitive data MUST NOT appear in audit entries, traces, or metrics.

```yaml
redaction_policy:
  always_redact:
    - "**/*.credentials"
    - "**/*.token"
    - "**/*.secret"
    - "**/*.password"
    - "**/*.api_key"
    - "safety_context.auth_scopes"  # log scope names, not token values

  conditional_redact:
    - field: "evidence_item.output"
      rule: "strip lines matching secret/token/password patterns"
      max_length: 65536

    - field: "context_in.shared_context"
      rule: "redact PII patterns (email, phone, SSN)"

    - field: "audit_entry.rationale"
      rule: "strip inline credentials, keep decision reasoning"

    - field: "snippet_ref.content"
      rule: "strip secrets from code snippets"

  enforcement:
    - "Redaction filter runs BEFORE audit write — never store then redact"
    - "Redaction filter runs BEFORE trace export"
    - "Failed redaction → block write + alert (never silently pass through)"
```

---

### 5.4 Audit Points

| Flow Step | Audit Event | Key Snapshot Data |
|-----------|-------------|-------------------|
| Pipeline created | `PIPELINE_CREATED` | Template ID, stage count, policy |
| Admission rejects | `ESCALATION` | Circuit breaker state, queue depth |
| Dispatch decision | `DISPATCH_DECISION` | All candidates, acceptance/rejection reasons, selected agent, policy version, ref freshness |
| Envelope sent | `DISPATCH_SENT` | dispatch_id, attempt_number, context_level |
| Agent times out | `DISPATCH_TIMEOUT` | Duration, deadline, cancel signal sent |
| Result received | `RESULT_RECEIVED` | Outcome, confidence, timing, artifact/evidence counts |
| Result invalid | `RESULT_INVALID` | Validation error, consecutive_invalid count, schema versions |
| Gate passes | `GATE_PASSED` | All 6 gate checks with evidence |
| Gate fails → retry | `GATE_FAILED` | Which checks failed, attempt budget remaining |
| Gate fails → reject | `GATE_REJECTED` | Reject reason, rewind target stage |
| Agent quarantined | `AGENT_QUARANTINED` | Instance ID, consecutive failures, last error |
| Human escalation | `ESCALATION` | Problem, impact, options, recommendation |
| Pipeline completes | `PIPELINE_COMPLETED` | Total timing, stages completed/skipped, risk summary |

---

### 5.5 Metrics

**Dispatch metrics (per pack_id, per task_type, per tenant_id):**

| Metric | Type | Description |
|--------|------|-------------|
| `a2a.dispatch.total` | Counter | Total dispatches |
| `a2a.dispatch.outcome` | Counter | Labeled by outcome class |
| `a2a.dispatch.latency_seconds` | Histogram | Dispatch to result received |
| `a2a.dispatch.attempts` | Histogram | Attempts per successful dispatch |
| `a2a.dispatch.timeout_total` | Counter | Dispatches that timed out |
| `a2a.dispatch.no_candidates_total` | Counter | No compatible agents available |
| `a2a.dispatch.time_to_first_dispatch_seconds` | Histogram | Task queued to first dispatch |

**Pipeline metrics (per template_id, per tenant_id):**

| Metric | Type | Description |
|--------|------|-------------|
| `a2a.pipeline.total` | Counter | Total pipelines started |
| `a2a.pipeline.completed_total` | Counter | Successfully completed |
| `a2a.pipeline.failed_total` | Counter | Failed or aborted |
| `a2a.pipeline.duration_seconds` | Histogram | Wall-clock start to finish |
| `a2a.pipeline.rejections` | Histogram | Review gate rejections per pipeline |
| `a2a.pipeline.stages_skipped_total` | Counter | Non-required stages skipped |
| `a2a.pipeline.deadline_breach_total` | Counter | Pipelines exceeding deadline |
| `a2a.pipeline.time_to_resolution_seconds` | Histogram | Task queued to pipeline complete |

**Gate metrics (per tier, per gate_name):**

| Metric | Type | Description |
|--------|------|-------------|
| `a2a.gate.total` | Counter | Total gate evaluations |
| `a2a.gate.passed_total` | Counter | Passed on first attempt |
| `a2a.gate.failed_total` | Counter | Failed (entered fix loop) |
| `a2a.gate.rejected_total` | Counter | Rejected (rewind) |

**Agent health metrics (per pack_id, per instance_id):**

| Metric | Type | Description |
|--------|------|-------------|
| `a2a.agent.health_status` | Gauge | Current health (enum as int) |
| `a2a.agent.capacity_utilization` | Gauge | active_tasks / max_tasks |
| `a2a.agent.quarantine_total` | Counter | Times quarantined |
| `a2a.agent.error_rate` | Gauge | Rolling 1-minute error rate |

**Escalation metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `a2a.escalation.total` | Counter | Total escalations |
| `a2a.escalation.resolution_time_seconds` | Histogram | Escalation to resolution |
| `a2a.escalation.unresolved` | Gauge | Currently open escalations |

---

### 5.6 Alerting

| Alert | Condition | Severity |
|-------|-----------|----------|
| High dispatch failure rate | `rate(a2a.dispatch.outcome{outcome="non_retryable"}) / rate(a2a.dispatch.total) > 0.10` over 5m | SEV2 |
| Pipeline deadline breach | `a2a.pipeline.deadline_breach_total` increments | SEV3 |
| All agents unhealthy | No HEALTHY instances for a pack_id sustained > 2m | SEV2 |
| Agent quarantined | `a2a.agent.quarantine_total` increments | SEV3 |
| Escalation backlog | `a2a.escalation.unresolved > 3` sustained 10m | SEV2 |
| No candidates available | `a2a.dispatch.no_candidates_total > 0` sustained 5m | SEV2 |
| Escalation resolution SLO | `a2a.escalation.resolution_time_seconds` p95 > 30m | SEV3 |

---

### 5.7 Dev vs Prod Observability

| Concern | Dev Adapter | Prod Adapter |
|---------|-------------|--------------|
| Trace backend | Structured JSON to console/file | OpenTelemetry → Jaeger/Tempo |
| Trace sampling | 100% (low volume) | Head-based or tail-based, configurable |
| Audit storage | Append to `docs/audit/<pipeline_id>.jsonl` | PostgreSQL append-only (constraints above) |
| Audit sampling | 100% (never sampled) | 100% (never sampled) |
| Metrics | Local in-memory counters + histograms, printed in progress report | OpenTelemetry → Prometheus/Grafana |
| Alerting | Inline warnings in orchestrator output | Full alert pipeline |
| Retention | Session-scoped | Policy-driven: per-tenant + legal overrides. Default: audit 7y, metrics 90d, traces 30d |
| Redaction | Same policy, enforced pre-write | Same policy, enforced pre-write |

---

## 6. Validation & CI

### 6.1 Proto Validation

| Check | Tool | Gate |
|-------|------|------|
| Breaking changes | `buf breaking --against .git#branch=main` | PR blocked on break |
| Lint | `buf lint` | PR blocked on violation |
| Schema validation | `buf validate` (protovalidate rules) | PR blocked on invalid |

### 6.2 Conformance Tests

| Test | Purpose |
|------|---------|
| Golden test vectors | Predefined TaskEnvelope/AgentResult pairs validated in both protobuf binary and protobuf JSON |
| Cross-language round-trip | Python ↔ TypeScript: serialize → deserialize → assert equality, including optional/oneof presence |
| Adapter conformance | Same input contract produces schema-valid outputs in both dev and prod adapters |

### 6.3 Transport Strategy

| Context | Transport | Format |
|---------|-----------|--------|
| Internal (orchestrator ↔ agent) | gRPC | Protobuf binary |
| Edge / dev tools | HTTP + JSON | Protobuf JSON mapping |
| Async workloads | Event bus (Redis Streams / Kafka) | Serialized proto envelope |

---

## 7. Evolution Path

| Phase | Scope | Trigger |
|-------|-------|---------|
| **Phase 1 (current)** | Hub-and-spoke orchestrator → specialist. Serial dispatch in dev, parallel in prod. | Now |
| **Phase 2** | Orchestrator-approved peer handoffs. Agents can request handoff; orchestrator validates and logs. | Many parallel tasks, high orchestrator latency |
| **Phase 3** | Full mixed mode. Direct agent-to-agent with policy enforcement at both ends. | Scale + mature observability + proven guardrails |

---

## 8. Summary

| Principle | Rule |
|-----------|------|
| Single canonical contract | Proto defines all messages. JSON Schema is generated, never hand-maintained. |
| Orchestrator owns all decisions | Agents never dispatch to each other. Orchestrator controls routing, context, retry. |
| Evidence before claims | Every AgentResult must include evidence. `none_with_reason` for hard failures. |
| Adaptive context | Required fields always travel. Optional context attached by HandoffPolicy. |
| Three-layer discovery | Static manifest (identity) + dynamic registry (runtime) + config routing (policy). |
| Pipeline chaining | Orchestrator-owned stage sequences with context propagation and rejection/rewind. |
| Immutable audit | Append-only, never sampled, redacted pre-write. |
| Transport-agnostic | gRPC internal, HTTP+JSON edge/dev, event bus async. Same envelope. |
| Lowest drift risk | Single proto source. Conformance tests catch adapter drift. |
