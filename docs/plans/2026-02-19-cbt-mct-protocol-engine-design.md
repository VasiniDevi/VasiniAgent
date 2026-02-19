# CBT + MCT Protocol Engine — Design Document

> **Date:** 2026-02-19
> **Scope:** Upgrade existing @ONAHELPBOT with structured CBT+MCT protocol flows
> **Approach:** A+ — Protocol Engine (code) + Practice content (YAML) + SQLite now, Postgres-ready
> **Research basis:** `Когно Ресерч .md`

---

## Key Decisions

| Decision | Choice |
|----------|--------|
| Scope | Upgrade existing @ONAHELPBOT |
| FSM model | Hybrid: strict safety layer + adaptive therapeutic flow |
| Practices | Core subset ~12 practices covering all 6 scenarios |
| Delivery UX | Interactive guided flow (inline buttons, timers). No mini apps. |
| Protocol modes | Both: structured programs + organic coaching |
| Storage | Extend SQLite, abstract via repository, Postgres-compatible schema |
| Technique selection | Deterministic rule engine selects, LLM only delivers text |
| Safety detection | Hard rules first + LLM classifier (haiku) second layer |

---

## Section 1: Architecture — 7-Module Pipeline

### Pipeline

```
Telegram Update
    │
    ▼
┌─────────────────────┐
│  1. Handler          │  Builds SessionContext, calls pipeline
│                      │  Per-user async lock (UserLock protocol)
│                      │  Idempotency: update_id / callback_query.id + UNIQUE in DB
│                      │  All writes in BEGIN IMMEDIATE transaction
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  2. SafetyClassifier │  ALWAYS FIRST. Hard gate. try/finally logging.
│     (rules + haiku)  │  → SAFE / CAUTION_MILD / CAUTION_ELEVATED / CRISIS
│                      │  Low confidence (<0.7) → CAUTION_MILD, never SAFE
│                      │  CRISIS → SafetyEventWriter (finally) → Escalation → SESSION_END
└──────────┬──────────┘
           ▼ (SAFE or CAUTION)
┌─────────────────────┐
│  3. ProtocolEngine   │  Hybrid FSM (code, not YAML)
│                      │  Session type classifier, state transitions
│                      │  Allowed transitions whitelist enforced
│                      │  Re-entry rules from any state
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  4. RuleEngine       │  Deterministic decision logic (code)
│                      │  7-step selection: signals → filter → match → score → select
│                      │  Returns 1 primary + 1 backup
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  5. PracticeRunner   │  Single owner of practice_step
│                      │  Steps from versioned YAML catalogs
│                      │  Inline buttons, timers, checkpoints
│                      │  Persistent timer state in DB
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  6. LLM Adapter      │  Text generation strictly per LLMContract
│                      │  Does NOT decide transitions or techniques
│                      │  Response validation before send
│                      │  Circuit breaker: 3 failures/60s → degrade to templates
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  7. ProgressTracker  │  Writes: sessions, practice progress, homework,
│                      │  assessments, metrics, safety_events, validation_events
│                      │  Tracks: fallback_rate, validation_fail_rate
└─────────────────────┘
```

### Module Contracts

```python
@dataclass
class SessionContext:
    user_id: int
    session_id: str
    update_id: int
    risk_level: RiskLevel
    caution_level: CautionLevel           # none | mild | elevated (enum)
    current_state: DialogueState
    session_type: SessionType
    user_profile: UserProfile

@dataclass
class EngineDecision:
    state: DialogueState
    action: Action
    practice_id: str | None
    practice_step: int | None             # set by PracticeRunner only
    ui_mode: UIMode
    llm_contract: LLMContract
    reason_codes: list[str]
    confidence: float | None              # None for rule-based decisions
    decision_source: Literal["model", "rules", "heuristic"]

@dataclass
class ModuleError:
    module: str
    recoverable: bool
    error_code: str
    fallback_response: str | None
```

### Concurrency & Idempotency

- Per-user `asyncio.Lock` for v1 single-process. `UserLock` protocol abstraction for future swap to DB advisory lock / Redis lock at scale-out.
- Idempotency key: `update_id` for messages, `callback_query.id` for callbacks. UNIQUE index in `processed_events`. Check+insert in same BEGIN IMMEDIATE transaction.
- Lock dict cleanup: TTL-based eviction for idle users.

---

## Section 2: Hybrid FSM — States, Transitions, Entry/Exit Criteria

### Two-Layer Policy

**Layer 1 — Hard Guardrail (deterministic):** Risk/safety checks, escalation rules, crisis routing.

**Layer 2 — Therapeutic Flow (adaptive FSM):** Formulation, goals, practice, reflection, homework. Can skip/reorder based on user profile and session memory.

### States

**Hard Layer:**

| State | Entry | Exit | Owner |
|-------|-------|------|-------|
| SAFETY_CHECK | Every incoming message | risk_level determined | SafetyClassifier |
| ESCALATION | CRISIS from any state | resources_sent OR handoff_attempted + status: resolved/unresolved/no_response | SafetyClassifier + SafetyEventWriter |

**Adaptive Layer:**

| State | Entry | Exit | Skip rules |
|-------|-------|------|------------|
| INTAKE | New user OR first session | Problem captured + baseline scores | returning → skip. returning_long_gap → short re-intake. |
| FORMULATION | INTAKE complete OR returning user | ≥1 maintaining cycle identified | quick_checkin with existing formulation → skip to MODULE_SELECT |
| GOAL_SETTING | FORMULATION complete | Micro-goal + time budget set | Returning with active goal → skip |
| MODULE_SELECT | GOAL complete | RuleEngine selected primary + backup | Active practice in progress → skip to PRACTICE |
| PRACTICE | Module selected OR resume (guarded) | All steps completed OR user skips | Never skipped. Resume guard: checkpoint_exists AND version compatible (patch/minor). Major → restart. |
| REFLECTION | PRACTICE complete | User rated outcome 0-10 + "what noticed" | Skippable with reason_code (timeout, crisis_reentry, user_stop) |
| REFLECTION_LITE | Partial/interrupted practice | Brief check-in done | Used instead of REFLECTION for incomplete practices |
| HOMEWORK | REFLECTION/REFLECTION_LITE complete | Assignment set OR user declines | User declines → skip, log reason |
| SESSION_END | Terminal state | (terminal) | Technical terminal-only state. Zero user-facing messages. All exits lead here. |

### Allowed Transitions Whitelist

```
SAFETY_CHECK    → ESCALATION | INTAKE | FORMULATION | PRACTICE (resume, guarded)
ESCALATION      → SESSION_END
INTAKE          → FORMULATION
FORMULATION     → GOAL_SETTING
GOAL_SETTING    → MODULE_SELECT
MODULE_SELECT   → PRACTICE
PRACTICE        → REFLECTION | REFLECTION_LITE
REFLECTION      → HOMEWORK
REFLECTION_LITE → HOMEWORK
HOMEWORK        → SESSION_END

Any state       → SAFETY_CHECK (re-entry triggers)
Any state       → SESSION_END (user_stop, timeout)
```

SAFETY_CHECK → MODULE_SELECT NOT allowed for new_user / returning_long_gap. Must go through FORMULATION.

### Re-entry Triggers

| Trigger | Action |
|---------|--------|
| Distress reported 8+ | → SAFETY_CHECK |
| Delta +3 from baseline within session | → SAFETY_CHECK |
| Panic keywords | → SAFETY_CHECK |
| Repeated hopelessness (2+ in current session, session-scoped TTL) | → SAFETY_CHECK |
| User says "stop" / "хватит" | → save resumable state → SESSION_END |
| No response 15 min during PRACTICE (from last_user_activity_at) | → pause, checkpoint, resumable |
| No response 30 min outside PRACTICE (from last_user_activity_at) | → SESSION_END |

### Session Type Classifier

| Type | Detection | Flow |
|------|-----------|------|
| new_user | No profile in DB | Full: INTAKE → all states |
| returning | Profile exists, last session < 14 days | Skip INTAKE → FORMULATION or MODULE_SELECT |
| returning_long_gap | Profile exists, last session >= 14 days | Short re-intake → FORMULATION |
| quick_checkin | Proactive check-in triggered | SAFETY → mood → if stable: encouragement + homework reminder → SESSION_END |
| crisis | SAFETY_CHECK returns CRISIS | SAFETY → ESCALATION → SESSION_END |
| resume | Incomplete practice_session (guarded) | SAFETY → resume PRACTICE from checkpoint |

### State Transition Audit

```python
@dataclass
class StateTransition:
    event_id: str                    # uuid, idempotency
    transition_seq: int              # monotonic per session
    session_id: str
    from_state: DialogueState
    to_state: DialogueState
    trigger: str
    reason_codes: list[str]
    timestamp: datetime              # UTC
    skipped: list[SkippedState]      # [{state, reason_code}]
```

---

## Section 3: Decision Rules + Practice Catalog

### 3.1 Selection Pipeline (7 steps, deterministic)

```
1. Collect signals → SessionContext
2. Hard filter → eligible only (risk, caution, readiness, time, prerequisites, safety_overrides)
3. Cycle match → first-line practices for maintaining_cycle
4. Score → normalized 0-1 per candidate
5. Select → 1 primary + 1 backup (tie-breaker: lower priority_rank)
6. PracticeRunner executes primary (fallback to backup if declined)
7. ProgressTracker writes unified outcome
```

LLM does NOT participate in selection. RuleEngine selects, LLM only generates text.

### 3.2 Decision Rules

**Rule 1 — Distress gates:**

| Distress | Allowed | Blocked |
|----------|---------|---------|
| 8-10 | Stabilization: A3, U2, A2 | Cognitive restructuring, exposure, experiments |
| 4-7 | A3, C2, C5, B1, A6, M2, M3 | Full exposure, deep Socratic |
| 0-3 | All techniques | None |

**Rule 2 — Maintaining cycle first-line:**

| Cycle | First line | Second line |
|-------|------------|-------------|
| Rumination | A2, A3, M2 | A1, B1 |
| Worry | A2, A3, C2 | A1, C3 |
| Avoidance | C3, B1 | C1 |
| Perfectionism | C5, C3 | M2 |
| Self-criticism | C5, A3 | C1 |
| Symptom fixation | A6, A1, A3 | C2 |

**Rule 3 — Time budget:**

| Budget | Eligible |
|--------|----------|
| 2 min | U2, M3, A2 |
| 5 min | All 2-min + A3, C5 |
| 10 min | All 5-min + A1, C1, M2 |
| 20 min | All 10-min + C3, full session |

**Rule 4 — Readiness:**

| Readiness | Policy |
|-----------|--------|
| Precontemplation | Psychoeducation + M3 + U2 |
| Contemplation | M2 + C5 + A3 |
| Action | Full catalog per rules |
| Maintenance | M3 + A2/A3 refresher + homework review. R-category in v1.1. |

**Rule 5 — CAUTION:**

| Level | Restriction |
|-------|-------------|
| Mild | Flag + monitoring instruction. All practices allowed. |
| Elevated | Block exposure, confrontation. Stabilization + soft cognitive only. Mandatory re-check after practice. |

### 3.3 Scoring (normalized 0-1)

```
score = clip(0, 1,
    cycle_match    * 0.4
  + effectiveness  * 0.3
  - repetition     * 0.2
  + novelty        * 0.1
)
```

Tie-breaker: lower `priority_rank` (explicit field in YAML, not string comparison).

### 3.4 Practice Catalog v1 (12 practices)

Category enum: `monitoring | attention | cognitive | behavioral | micro`

| ID | Name | Category | Duration | Cycles | priority_rank |
|----|------|----------|----------|--------|---------------|
| M2 | Мониторинг руминации | monitoring | 2-5m | rumination, worry | 10 |
| M3 | Шкала настроения | monitoring | 1m | all | 5 |
| A1 | ATT (тренировка внимания) | attention | 10-12m | rumination, worry, symptom_fixation | 20 |
| A2 | Отложенная руминация | attention | 2-5m | rumination, worry | 15 |
| A3 | Detached Mindfulness | attention | 2-5m | rumination, worry, self_criticism | 16 |
| A6 | SAR (переключение) | attention | 2-3m | symptom_fixation, avoidance | 25 |
| C1 | Сократический диалог | cognitive | 5-10m | avoidance, perfectionism | 30 |
| C2 | Декатастрофизация | cognitive | 5-7m | worry | 31 |
| C3 | Поведенческий эксперимент | cognitive | 10-20m | avoidance, worry, perfectionism | 35 |
| C5 | Двойной стандарт | cognitive | 3-5m | self_criticism, perfectionism | 28 |
| B1 | Поведенческая активация | behavioral | 5-10m | avoidance, rumination | 22 |
| U2 | 3-3-3 заземление | micro | 60s | all (stabilization) | 1 |

v1.1 backlog: A4, A5, B2, B3, B4, C4, M1, R1-R3, U1/U3-U6.

### 3.5 Practice YAML Schema

```yaml
id: A2
version: "1.0"                          # semver
step_schema_hash: "sha256:abc123"
name_ru: "Отложенная руминация"
name_en: "Worry Postponement"
category: attention
goal: "Прерывание цикла руминации"
duration_min: 2
duration_max: 5
priority_rank: 15

prerequisites:
  needs_formulation: true
  min_time_budget: 2
  min_readiness: contemplation

safety_overrides:
  blocked_in_caution_elevated: false
  blocked_if_distress_gte: null

maintaining_cycles: [rumination, worry]

steps:
  - index: 1
    instruction_ru: "Заметьте: «я снова кручу мысли»."
    ui_mode: text
    checkpoint: false
    fallback:
      user_confused: "Руминация — это когда одна мысль крутится по кругу. Замечаете такое?"
      cannot_now: "Ничего, попробуем позже."
      too_hard: "Давайте начнём проще — просто скажите, о чём сейчас думаете."
  # ... remaining steps with all 3 fallback keys mandatory

outcome:
  pre_rating: {type: rating, label: "Интенсивность руминации", scale: "0-10"}
  post_rating: {type: rating, label: "Интенсивность руминации", scale: "0-10"}
  # delta = pre_raw - post_raw (positive = improvement), computed on read, both raw stored
  completed: bool
  drop_reason: null
  tracking: {type: counter, label: "Успешных откладываний/день"}

resume_compatibility:
  practice_id: A2
  version: "1.0"
  step_schema_hash: "sha256:abc123"
```

**YAML validation at startup (fail-fast):** enum values, required fields, step index continuity (1..N no gaps), all fallback keys present, button action enum, version format.

**Button actions enum:** `next | fallback | branch_extended | branch_help | backup_practice | end`

**Versioning policy:** semver. patch/minor compatible → resume allowed. major mismatch → restart practice.

---

## Section 4: Safety System

### 4.1 SafetyClassifier — Two-layer detection

**Layer 1 — Hard rules (instant, first):**

| Pattern group | Classification |
|--------------|----------------|
| Suicide explicit | CRISIS → S1 |
| Self-harm | CRISIS → S1 |
| Violence to others | CRISIS → S2 |
| Psychosis indicators | CRISIS → S3 |
| Domestic violence | CRISIS → S6 |

**Layer 2 — LLM classifier (haiku, if Layer 1 = no match):**

```json
{
  "risk_level": "SAFE|CAUTION_MILD|CAUTION_ELEVATED|CRISIS",
  "protocol": null or "S1-S7",
  "immediacy": "none|possible|imminent",
  "signals": [],
  "confidence": 0.0-1.0
}
```

**Classification logic:**
```
hard_rules_match         → use hard rules (source: "rules")
haiku.confidence >= 0.7  → use haiku result (source: "model")
haiku.risk_level == CRISIS → escalate (safety > precision)
haiku.confidence < 0.7   → CAUTION_MILD (NEVER SAFE when uncertain)
```

### 4.2 Escalation Protocols S1-S7

| Protocol | Trigger | Default level | Notes |
|----------|---------|---------------|-------|
| S1 | Suicide/Self-harm | CRISIS | Acknowledge → crisis contacts → safety question |
| S2 | Violence to others | CRISIS | → Emergency 112 |
| S3 | Psychosis/Mania | CRISIS | Don't argue, no cognitive techniques |
| S4 | Severe depression | CAUTION_ELEVATED | CRISIS only if suicidal OR unable to maintain basic safety |
| S5 | Withdrawal | CRISIS | → Emergency 103/112 |
| S6 | Domestic violence | CRISIS | Never "talk to partner". Never coach victim behavior. |
| S7 | Eating disorders | CAUTION_ELEVATED | Behavioral indicators only, no BMI thresholds |

Resources: locale-aware `ResourceResolver`. Stored in `packs/wellness-cbt/resources/{locale}.yaml`, versioned, `last_verified_at` per resource.

Human handoff: `OFFERED → ACCEPTED → CONNECTED | FAILED | TIMEOUT` or `OFFERED → DECLINED`.

### 4.3 Post-escalation — canonical rules (single source of truth)

1. **CRISIS (imminent):** 100% static response, zero LLM generation. No techniques, no therapeutic interventions.
2. **CRISIS (non-imminent):** Static core + optional LLM empathetic intro if available within timeout.
3. **Post-CRISIS stabilization:** Short grounding instructions permitted ("Пока ждёте помощь: дышите медленно"). Not therapy.
4. **CRISIS sessions:** Non-resumable as PRACTICE. New session starts fresh.
5. **SafetyEventWriter:** try/finally — always persists regardless of pipeline outcome.

All other sections reference this block rather than restating these rules.

### 4.4 CAUTION Policy (enum, deterministic classification)

| Level | Detection | Restrictions | Re-check |
|-------|-----------|-------------|----------|
| CAUTION_MILD | Ambiguous signal, low-confidence model | Flag + monitoring. All practices. | At next REFLECTION |
| CAUTION_ELEVATED | Hopelessness, passive death wish, high distress + isolation | Block exposure/confrontation. Stabilization + soft cognitive only. | After every step. 2 consecutive elevated → CRISIS only if 30-min window AND intent/plan/imminence signals. |

### 4.5 Content Governance

Never: diagnose, advise medication, claim to replace therapy, guarantee outcomes, provide legal interpretations (can provide official contacts), process trauma / interpret dreams, provide self-harm "how-to".

**Disclaimer (onboarding + repeated):** "Я не работаю 24/7 и не могу вызвать экстренные службы. Если вам нужна срочная помощь — звоните по номеру экстренной помощи."

### 4.6 safety_events fields

```
classifier_version, policy_version, message_locale, resource_set_version,
user_message_hash (SHA-256, always stored),
user_message_raw (optional, config flag, separate shorter retention + auto-redaction policy),
handoff_status, resolution, timestamp_utc
```

---

## Section 5: Database Schema + Repository Layer

### 5.1 Schema Rules

- IDs: TEXT UUIDs
- Timestamps: ISO-8601 TEXT (UTC). Postgres: TIMESTAMPTZ
- JSON: `_json` suffix, TEXT. Postgres: JSONB
- Booleans: `INTEGER NOT NULL DEFAULT 0 CHECK(x IN (0,1))`
- FK: `ON DELETE RESTRICT` (audit)
- Enums: CHECK constraints
- Ratings: `CHECK(x BETWEEN 0 AND 10)`
- Delta: computed on read, not stored
- metadata_json: max 4KB, validated key whitelist
- created_at + updated_at on key tables

### 5.2 Tables

```sql
CREATE TABLE dialogue_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_type TEXT NOT NULL CHECK(session_type IN
        ('new_user','returning','returning_long_gap','quick_checkin','crisis','resume')),
    current_state TEXT NOT NULL CHECK(current_state IN
        ('SAFETY_CHECK','ESCALATION','INTAKE','FORMULATION','GOAL_SETTING',
         'MODULE_SELECT','PRACTICE','REFLECTION','REFLECTION_LITE','HOMEWORK','SESSION_END')),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    end_reason TEXT CHECK(end_reason IN ('completed','user_stop','timeout','crisis_reentry') OR end_reason IS NULL),
    last_user_activity_at TEXT NOT NULL,
    resumable INTEGER NOT NULL DEFAULT 0 CHECK(resumable IN (0,1)),
    resume_practice_id TEXT,
    resume_step_index INTEGER,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_sessions_active ON dialogue_sessions(user_id, ended_at, last_user_activity_at);
CREATE UNIQUE INDEX idx_one_active_session ON dialogue_sessions(user_id) WHERE ended_at IS NULL;

CREATE TABLE state_transitions (
    event_id TEXT PRIMARY KEY,
    transition_seq INTEGER NOT NULL,
    session_id TEXT NOT NULL REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT NOT NULL,
    reason_codes_json TEXT NOT NULL,
    skipped_json TEXT,
    timestamp_utc TEXT NOT NULL,
    UNIQUE(session_id, transition_seq)
);
CREATE INDEX idx_transitions_session ON state_transitions(session_id, transition_seq);

CREATE TABLE practice_sessions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL,
    practice_id TEXT NOT NULL,
    practice_version TEXT NOT NULL,
    step_schema_hash TEXT NOT NULL,
    priority_rank INTEGER NOT NULL,
    current_step_index INTEGER NOT NULL DEFAULT 1,
    total_steps INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK(status IN ('in_progress','completed','dropped','paused')),
    pre_rating INTEGER CHECK(pre_rating BETWEEN 0 AND 10),
    post_rating INTEGER CHECK(post_rating BETWEEN 0 AND 10),
    drop_reason TEXT CHECK(drop_reason IN ('timeout','user_stop','too_hard','crisis_reentry') OR drop_reason IS NULL),
    timer_state_json TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_practice_status ON practice_sessions(user_id, status, started_at);

CREATE TABLE practice_checkpoints (
    id TEXT PRIMARY KEY,
    practice_session_id TEXT NOT NULL REFERENCES practice_sessions(id) ON DELETE RESTRICT,
    step_index INTEGER NOT NULL,
    user_response TEXT,
    button_action TEXT CHECK(button_action IN
        ('next','fallback','branch_extended','branch_help','backup_practice','end') OR button_action IS NULL),
    fallback_used TEXT CHECK(fallback_used IN ('user_confused','cannot_now','too_hard') OR fallback_used IS NULL),
    timestamp_utc TEXT NOT NULL,
    UNIQUE(practice_session_id, step_index)
);

CREATE TABLE homework (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    practice_id TEXT NOT NULL,
    assignment_text TEXT NOT NULL,
    frequency TEXT CHECK(frequency IN ('daily','2x_day','weekly','once') OR frequency IS NULL),
    assigned_at TEXT NOT NULL,
    due_at TEXT,
    status TEXT NOT NULL DEFAULT 'assigned'
        CHECK(status IN ('assigned','completed','partial','skipped','expired')),
    completion_rating INTEGER CHECK(completion_rating BETWEEN 0 AND 10),
    completion_note TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_homework_pending ON homework(user_id, status, due_at);

CREATE TABLE protocol_progress (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    protocol_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('structured','organic')),
    current_session_number INTEGER NOT NULL DEFAULT 1,
    total_sessions INTEGER,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','completed','paused','abandoned')),
    maintaining_cycle TEXT,
    started_at TEXT NOT NULL,
    last_session_at TEXT,
    completed_at TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_protocol_user ON protocol_progress(user_id, status);

CREATE TABLE assessments (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    instrument TEXT NOT NULL CHECK(instrument IN ('PHQ-2','GAD-2','custom_mood','custom_rumination')),
    score INTEGER NOT NULL,
    max_score INTEGER NOT NULL,
    responses_json TEXT NOT NULL,
    administered_at TEXT NOT NULL,
    session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE RESTRICT
);
CREATE INDEX idx_assessments_user ON assessments(user_id, instrument, administered_at);

CREATE TABLE safety_events (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    risk_level TEXT NOT NULL CHECK(risk_level IN ('SAFE','CAUTION_MILD','CAUTION_ELEVATED','CRISIS')),
    protocol_id TEXT CHECK(protocol_id IN ('S1','S2','S3','S4','S5','S6','S7') OR protocol_id IS NULL),
    immediacy TEXT CHECK(immediacy IN ('none','possible','imminent') OR immediacy IS NULL),
    signals_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('rules','model')),
    classifier_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    message_locale TEXT NOT NULL,
    resource_set_version TEXT NOT NULL,
    user_message_hash TEXT NOT NULL,
    user_message_raw TEXT,
    bot_response_text TEXT,
    handoff_status TEXT CHECK(handoff_status IN
        ('offered','accepted','connected','failed','timeout','declined') OR handoff_status IS NULL),
    resolution TEXT CHECK(resolution IN ('resolved','unresolved','no_response') OR resolution IS NULL),
    timestamp_utc TEXT NOT NULL
);
CREATE INDEX idx_safety_user ON safety_events(user_id, timestamp_utc);
CREATE INDEX idx_safety_crisis ON safety_events(risk_level) WHERE risk_level = 'CRISIS';

CREATE TABLE processed_events (
    idempotency_key TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
CREATE INDEX idx_processed_ttl ON processed_events(processed_at);

CREATE TABLE technique_history (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    practice_id TEXT NOT NULL,
    times_used INTEGER NOT NULL DEFAULT 0,
    avg_effectiveness REAL,
    last_used_at TEXT,
    UNIQUE(user_id, practice_id)
);
CREATE INDEX idx_technique_user ON technique_history(user_id);

CREATE TABLE validation_events (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE RESTRICT,
    validator_version TEXT NOT NULL,
    check_name TEXT NOT NULL,
    passed INTEGER NOT NULL CHECK(passed IN (0,1)),
    failure_reason TEXT,
    llm_response_hash TEXT,
    timestamp_utc TEXT NOT NULL
);
```

### 5.3 Repository Layer

```python
class UnitOfWork(ABC):
    async def __aenter__(self) -> Self: ...      # BEGIN IMMEDIATE
    async def __aexit__(self, *exc) -> None: ... # COMMIT or ROLLBACK
    def sessions(self) -> SessionRepository: ...
    def practices(self) -> PracticeRepository: ...
    def safety(self) -> SafetyRepository: ...
    def homework(self) -> HomeworkRepository: ...
    def assessments(self) -> AssessmentRepository: ...
    def techniques(self) -> TechniqueHistoryRepository: ...
    def protocols(self) -> ProtocolRepository: ...
    def idempotency(self) -> IdempotencyRepository: ...

class IdempotencyRepository(ABC):
    async def is_processed(self, key: str) -> bool: ...
    async def mark_processed(self, key: str) -> None: ...

class TechniqueHistoryRepository(ABC):
    async def upsert_stats(self, user_id: int, practice_id: str, delta: int) -> None: ...
    # atomic INSERT ... ON CONFLICT DO UPDATE
```

### 5.4 Retention (config-driven)

```yaml
retention_policy:
  safety_events: {days: null, policy: "config"}
  safety_events_raw_text: {days: 7, policy: "auto_redact"}   # separate from hash
  dialogue_sessions: {days: null, policy: "config"}
  state_transitions: {days: 90}
  practice_checkpoints: {days: 90}
  processed_events: {days: 1}
```

### 5.5 Migration Path

v1: SQLite + SQLiteXxxRepository. v1.1: sqlite_to_postgres.py. v2: PostgresXxxRepository + config switch, zero business logic changes.

---

## Section 6: LLM Adapter — Contract-Bound Generation

### 6.1 LLMContract

```python
@dataclass
class LLMContract:
    dialogue_state: str
    generation_task: str
    instruction: str
    practice_context: str | None
    user_response_to: str | None
    persona_summary: str                    # compact persona layer
    user_summary: str
    recent_messages: list[dict]             # last 5 only
    max_messages: int                       # 1-3
    max_chars_per_message: int              # 500
    language: str
    must_include: list[str]
    must_not: list[str]
    ui_mode: str
    buttons: list[dict] | None
    timer_seconds: int | None
```

### 6.2 Per-State Contracts

| State | generation_task | must_include | must_not |
|-------|----------------|-------------|----------|
| INTAKE | ask_intake_question | mood/anxiety rating | diagnose |
| FORMULATION | explore_cycle | behavior→emotion→thought link | label as disorder |
| GOAL_SETTING | set_micro_goal | time budget question | promise outcomes |
| MODULE_SELECT | present_technique | consent question | force participation |
| PRACTICE | deliver_step | step content from YAML | skip/add steps |
| PRACTICE (timer) | guide_timer | start/end cue | lengthy mid-exercise text |
| REFLECTION | ask_reflection | post-rating 0-10 + "what noticed" | evaluate experience |
| REFLECTION_LITE | brief_reflection | how they feel now | pressure to complete |
| HOMEWORK | assign_homework | specific what/when/frequency | vague instructions |
| ESCALATION | deliver_escalation | resources + safety question | techniques (see Section 4.3) |

### 6.3 LLM Tier Routing

| Context | Model |
|---------|-------|
| SafetyClassifier | Haiku |
| INTAKE simple questions | Haiku |
| PRACTICE / FORMULATION / REFLECTION | Sonnet |
| ESCALATION (non-imminent, optional framing) | Sonnet |
| ESCALATION (imminent) | No LLM — static only |

### 6.4 Response Validation

Checks: length, must_include, must_not, no_diagnosis, no_medication, language, state_alignment (correct CTA/buttons), actionability (exactly one next step), safety_lexicon (no accusatory/dismissive at CAUTION/CRISIS).

`validator_version` tracked. Failures → `validation_events` table.

Fail: recoverable → 1 retry with correction + forced_locale_override if language mismatch. Non-recoverable → state-specific fallback.

### 6.5 Fallback Responses

| State | Fallback |
|-------|----------|
| PRACTICE | template_wrapper(empathetic frame + instruction_ru) + buttons |
| INTAKE | "Расскажите, что вас сейчас беспокоит?" |
| FORMULATION | "Давайте разберёмся: что обычно происходит, когда вам плохо?" |
| GOAL_SETTING | "Чего бы вы хотели достичь сегодня? Даже маленький шаг считается." |
| MODULE_SELECT | "Могу предложить: (A) {practice_1} — {goal_1}, (B) {practice_2} — {goal_2}. Что ближе?" |
| REFLECTION | "Как это было для вас? Оцените от 0 до 10." |
| HOMEWORK | "Попробуйте практиковать то, что мы делали, один раз до следующего разговора." |
| ESCALATION | Static only (see Section 4.3) |

max_repeat_count = 2. After → "Похоже, сейчас не лучшее время. Давайте вернёмся позже?" → SESSION_END.

### 6.6 Circuit Breaker

LLM timeout: 3s. 3 failures in 60s → degrade to templates until half-open.

---

## What YAML Stores vs What Code Owns

| YAML (content, declarative) | Code (logic, deterministic) |
|-----------------------------|----------------------------|
| Practice step texts, button labels, timer params | FSM states + transitions |
| Practice metadata (prerequisites, safety_overrides) | Safety classification logic |
| Crisis resource contacts per locale | Decision rules + scoring |
| Fallback texts | State transition enforcement |
| Outcome schema per practice | Concurrency + idempotency |
| Practice version + step_schema_hash | Response validation |

Protocol packs versioned: `version` + `compatible_engine_version`.
