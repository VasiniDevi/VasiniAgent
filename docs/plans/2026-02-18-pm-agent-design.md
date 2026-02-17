# PM Agent — Design Document

**Date:** 2026-02-18
**Status:** Approved
**Goal:** Claude Code skill that acts as an autonomous project manager — reads design/plan docs, dispatches sub-agents to implement tasks, reviews all code with tiered depth, enforces quality gates, and drives a project to completion with minimal human intervention.

---

## 1. Overview

A single comprehensive Claude Code skill (`pm-agent`, invoked as `/pm-agent`) that orchestrates end-to-end project delivery. The PM agent owns all decisions about scope, sequencing, and quality — sub-agents only execute. Human retains final merge authority.

### Input
- Path to design doc + plan doc in `docs/plans/`
- PM reads the plan, determines what's done vs. remaining, and drives execution autonomously

### Core Loop
```
ORCHESTRATE → DISPATCH → REVIEW GATE → PROGRESS + NEXT
     ↑                                        │
     │            (loop per task)              │
     └────────────────────────────────────────┘
                       │
                 queue empty?
                       ↓
               FINAL RELEASE GATE
                       ↓
              human sign-off to merge
```

---

## 2. State Store

Persists across the session. Source of truth for all PM decisions.

```yaml
state_store:
  global:
    plan_id: string                    # plan document identifier
    baseline_sha: string               # SHA at session start
    current_sha: string                # SHA after latest commit
    shared_context_block: string       # compact project context (built once)
    unresolved_risks: Risk[]           # accumulated across tasks
    checkpoint_tags: string[]          # tags after passed critical tasks

  per_task:
    task_id: string
    status: pending | ready | in_progress | completed | failed | escalated
    tier: critical | normal | low
    retry_count: number                # current fix attempts (max 2)
    decision_log: string[]             # why PM made each decision
    artifacts: string[]                # files produced
    known_risks: Risk[]                # risks identified during this task
    review_notes: ReviewNote           # what changed / risks / rollback
    commit_sha: string | null          # set after commit
    duration_ms: number                # dispatch → gate pass
    ownership: string                  # module/service affected

  Risk:
    id: string
    description: string
    severity: critical | normal | low
    status: open | mitigated | accepted
    source_task: string

  ReviewNote:
    summary: string                    # what changed (1-2 sentences)
    risks: string[]                    # identified risks
    rollback: string                   # rollback instructions
```

---

## 3. Phase 1: ORCHESTRATE

### Init (first run only)
1. Load design doc + plan doc from `docs/plans/`
2. Full baseline scan: `git log`, file tree, test results
3. Build **shared context block** (compact, stored once):
   - Project name, tech stack, conventions
   - Key file paths, module boundaries
   - Design principles + constraints
4. Diff plan tasks vs. codebase reality
   - For each task: `EXISTS` / `PARTIAL` / `MISSING`
5. Classify each task:
   - **CRITICAL:** auth, costs/finops, data integrity, migrations, infra, security, public API
   - **NORMAL:** features, handlers, integrations
   - **LOW:** UI copy, refactors, docs, config
6. Build dependency-aware execution queue (topological sort)

### Per-Cycle (before each dispatch)
- **Incremental diff only** — `git diff` since last task SHA (no full rescan)
- Update state store with new artifacts/changes
- Select next task from queue (respecting dependencies)

---

## 4. Phase 2: DISPATCH

### Task Contract

Every sub-agent receives a structured contract:

```yaml
task_contract:
  task_id: string
  title: string
  tier: critical | normal | low
  ownership: string                    # module/service this touches

  # What to build
  acceptance_criteria: string[]        # from plan doc
  expected_files:
    create: string[]
    modify: string[]
    delete: string[]

  # What NOT to build
  non_goals: string[]                  # explicit scope guard

  # Testing
  tests_to_add: string[]              # new tests sub-agent must write
  tests_to_run: string[]              # existing tests to execute

  # Definition of Done
  definition_of_done:
    - "Code implements all acceptance criteria"
    - "tests_to_add written and passing"
    - "tests_to_run all passing"
    - "Docs updated if public API or config changed"
    - "Migration + rollback notes if schema/infra changed"
    - "No TODO/FIXME without linked follow-up task"

  # I/O contract
  io_contract:
    dependencies: string[]             # what this task consumes
    artifacts: string[]                # what this task produces
    expected_interfaces: string[]      # APIs/types this exposes
    breaking_change: boolean           # does this break existing contracts?

  # Environment contract
  environment:
    lint_command: string               # e.g. "ruff check packages/agent-core"
    typecheck_command: string          # e.g. "mypy packages/agent-core"
    test_command: string               # e.g. "pytest packages/agent-core/tests"
    build_command: string | null       # if applicable

  # Context injection
  context:
    shared: string                     # compact shared context block (NOT re-scanned)
    task_delta: string                 # files to read, recent changes, prior decisions

  # Budgets
  retry_budget: 2                     # max fix attempts before escalation
  time_budget_ms: number              # timeout — PM interrupts if exceeded
  patch_size_limit: number            # max files changed — auto-split if exceeded

  # Security flags
  security_flags:
    touches_auth: boolean
    touches_schema: boolean
    touches_billing: boolean
    touches_secrets: boolean
    # Any true → auto-escalate tier to CRITICAL
```

### Dispatch Rules

1. **One sub-agent per task** — unless task exceeds patch_size_limit, then PM slices into subtasks first
2. **Serial:** critical tasks, tasks with dependencies
3. **Parallel:** independent low-risk tasks only, max 3 concurrent, locked by ownership area (not just file overlap — two tasks touching the same module/service cannot run in parallel)
4. **Sub-agent instructions:**
   - Use appropriate skills as the situation demands (TDD, debugging, verification — not a mandatory checklist)
   - Do NOT commit (commits owned by PM)
   - Return structured evidence, not just pass/fail
5. **Sub-agent returns:**
   - Files created / modified / deleted
   - Test results with key output lines (evidence)
   - Lint + typecheck results with key output lines
   - Blockers, ambiguities, or risks encountered
   - Self-assessment: `confident` / `uncertain` / `blocked`

### Escalation (pre-dispatch)
- Ambiguous requirements → STOP, escalate to human
- Depends on blocked task → skip, requeue, pick next
- No tasks available (all blocked) → STOP, present blockers
- Security flag detected → auto-escalate tier to CRITICAL before dispatch

### Human Escalation Format (all escalations use this template)
```
ESCALATION
Problem:     [what failed or is ambiguous]
Impact:      [what's blocked, downstream effects]
Options:     [2-3 concrete options]
Recommended: [PM's best judgment]
Blocking:    yes/no
```

---

## 5. Phase 3: REVIEW GATE

### Collect Evidence
1. Sub-agent output: files changed, test results, self-assessment, evidence lines, blockers
2. `git diff --stat` — actual changes vs. expected files
3. Auto-escalate tier to CRITICAL if changes touch: auth, schema/migrations, billing/finops, secrets/env, public API, infra/docker
4. Record raw evidence in state store for audit

### Minimum Gate (all tiers, mandatory, no exceptions)

| # | Gate | Check | Evidence Required |
|---|------|-------|-------------------|
| 1 | Plan alignment | Each acceptance criterion mapped to file + line reference | Criterion → code mapping |
| 2 | Tests (add) | `tests_to_add` written and passing | Test file paths + pass output |
| 3 | Tests (run) | `tests_to_run` executed, all pass | Test command output lines |
| 4 | Lint + typecheck | Environment contract commands pass, zero errors | Command output |
| 5 | No orphan TODOs | Grep changed files for `TODO/FIXME/HACK/XXX` — each has follow-up task | Grep results |
| 6 | Review note | What changed, risks, rollback present | Structured ReviewNote |

**ANY gate FAIL → enter Fix Loop. ALL gates PASS → proceed to Tier Review.**

### Tier Review

**CRITICAL:**
- Dispatch code-reviewer sub-agent (full diff review against design doc)
- Run ALL impacted test suites (not just new tests)
- Security check: no secrets in code, no injection vectors, no unvalidated input
- Data integrity: migrations reversible?
- Breaking change flagged → release notes artifact
- Must PASS all checks

**NORMAL:**
- Dispatch code-reviewer sub-agent (changed files + plan alignment)
- Run targeted test suites for affected modules (from ownership field)
- Quick scan: no obvious anti-patterns

**LOW:**
- PM reads diff directly (no reviewer agent)
- Sanity check: changes match task scope?
- If schema/API/security behavior changed → auto-escalate to NORMAL

### Fix Loop
```
Attempt 1:
  → Dispatch fix sub-agent with:
    - Specific failure evidence (gate ID + line refs)
    - Original task contract (scope guard)
    - Instruction: fix ONLY the flagged issues
  → Re-run failed gates + tier review

Attempt 2:
  → Same process, tighter scope

Attempt 3 (retry budget exhausted):
  → STOP — escalate to human (standard escalation format)
  → Retry counter stored in state store
  → Idempotent: restart resumes from last attempt, no duplication
```

### On Pass
- Gate result + review note → state store
- Signal to Phase 4: task ready for commit
- Artifacts list updated for downstream tasks

---

## 6. Phase 4: PROGRESS + NEXT

### Commit Policy

**Commit message format:**
```
type(scope): short description

Refs: task-<id>
Review: <artifact-file-path>
```
- Subject line: strict conventional commit format
- Detailed review data (criteria, tests, risks, rollback) written to a **review artifact file** (`docs/reviews/<task-id>-review.md`), NOT in commit body

**Branch convention:**
```
feat/<plan-id>/<task-id>-short-name
Example: feat/wellness-cbt/task-07-voice-pipeline
```

**Branch rules:**
- High-blast-radius critical tasks: separate branch, held for staged integration after all gates pass
- Other critical tasks: plan working branch (reduces cherry-pick overhead)
- Normal + low tasks: plan working branch
- Never force-push. Never amend published commits.

**Checkpoint tags (after passed critical tasks):**
```
pm/<plan-id>/checkpoint-<task-id>
```

### State Update
After each commit:
- Mark task `completed` in state store
- Record: `commit_sha`, `files_changed`, `review_tier`, `review_result`, `retry_count`, `review_note`, `duration_ms`, `artifacts`
- Update `current_sha` in global state
- Clear retry counter
- Update `unresolved_risks[]` if review flagged any
- Record `duration_ms` for timeout/SLA tracking

### Queue Management

**Anti-starvation rule:** After every 3 critical/normal completions, allow one ready low-risk task (prevents low tasks from waiting forever).

**Unblock dependents:**
- Check all queued tasks' dependencies
- If all deps satisfied → mark `ready`
- Re-classify if needed (new info may change tier/scope of downstream tasks)

**Parallel check:**
- 2+ independent LOW tasks ready?
- No shared ownership area (module/service lock, not just file overlap)?
- → Dispatch in parallel (max 3)

**Next task priority:**
```
CRITICAL (serial) > NORMAL > LOW
Within same tier: dependency order first, then plan document order
Anti-starvation exception: 1 LOW after every 3 CRITICAL/NORMAL
```

### Progress Report

**Triggered by:**
- Every 3 completed tasks OR every 30 minutes (whichever first)
- After any critical task completes
- After any human escalation resolves
- On explicit user request

**Format:**
```
PROGRESS — <plan-name>
Completed: X/Y tasks
In progress: [list]
Blocked: [list + reason]
Unresolved risks: [count, top 3 by severity]
Estimated remaining: [count by tier]
```

### Loop or Terminate

**Tasks remaining?**
- YES → loop back to Phase 2 (Dispatch)
- NO → enter Final Release Gate

---

## 7. Final Release Gate

### Checks
1. **Full test suite** — all packages
2. **Full lint + typecheck** — all packages
3. **Build passes** — if applicable
4. **Migration safety:**
   - Forward migration dry-run
   - Rollback validation (where applicable)

### Failure Policy
If final gate fails → automatically open remediation tasks and re-enter the Phase 2-3-4 loop. Not a dead end.

### Unresolved Risk Audit
- List all risks from state store
- Each risk: `mitigated` / `accepted` / `open`
- Any `open` risk on CRITICAL task → STOP, escalate to human

### Completeness Check
- Every plan task has status: `completed`
- Every acceptance criterion mapped to code
- No orphan `TODO/FIXME` without follow-up task

### Release Manifest (machine-readable artifact)
```yaml
# docs/releases/<plan-id>-release.yaml
plan_id: string
plan_doc: string                       # path to plan doc
design_doc: string                     # path to design doc
completed_at: ISO-8601
tasks:
  - task_id: string
    commit_sha: string
    review_artifact: string            # path to review file
    tier: critical | normal | low
    breaking_change: boolean
tests_run: number
tests_passed: number
lint_clean: boolean
typecheck_clean: boolean
build_clean: boolean
risks:
  - id: string
    status: mitigated | accepted
    description: string
breaking_changes: string[]
migration_steps: string[]
rollback_plan: string                  # per-component instructions
recommended_next: string[]             # what to do after this release
```

### Handoff
```
RELEASE SUMMARY — <plan-name>

Tasks: X/X completed
Commits: [count] (see release manifest for full list)
Breaking changes: [list or "none"]
Open risks: [list or "none — all mitigated/accepted"]
Migration: [steps or "none required"]
Rollback: see release manifest
Recommended next: [list]

Artifacts:
  - Release manifest: docs/releases/<plan-id>-release.yaml
  - Review notes: docs/reviews/<task-id>-review.md (per task)
```

**PM does NOT merge to main autonomously. Human owns that decision.**

---

## 8. Skill Integration

The PM agent uses existing Claude Code capabilities situationally:

| Situation | Tool / Approach |
|-----------|----------------|
| Implement a task | Task tool → sub-agent with task contract |
| Review code (critical/normal) | Task tool → code-reviewer sub-agent |
| Fix failed gate | Task tool → fix sub-agent with failure evidence |
| Run tests/lint/typecheck | Bash tool with environment contract commands |
| Track progress | TaskCreate / TaskUpdate / TaskList tools |
| Search codebase | Grep / Glob / Explore agents as needed |
| Debug failures | Systematic approach, driven by evidence |
| Verify completion | Fresh verification — evidence before claims |

Skills (TDD, debugging, verification, etc.) are used by sub-agents as the situation demands — not a mandatory checklist per task.

---

## 9. Configuration

```yaml
pm_config:
  max_parallel_agents: 3               # concurrent low-risk dispatches
  retry_budget: 2                      # fix attempts before escalation
  anti_starvation_interval: 3          # low task allowed after N critical/normal
  progress_report_task_interval: 3     # report every N tasks
  progress_report_time_interval_min: 30 # or every N minutes
  patch_size_limit_files: 15           # auto-split if exceeded
  checkpoint_tags: true                # tag after critical tasks
  review_artifacts_dir: "docs/reviews"
  release_manifest_dir: "docs/releases"
```

---

## 10. Summary

| Principle | Rule |
|-----------|------|
| Ownership | PM owns all decisions. Sub-agents only execute. |
| Scope | Sub-agents receive tight contracts with non-goals. |
| Quality | Tiered review: critical (full), normal (targeted), low (sanity). |
| Gates | 6 mandatory gates per task. No exceptions. |
| Commits | Separate from review. Atomic per task. Details in artifacts, not commit body. |
| Retry | Max 2 fix attempts, then human escalation. |
| Merge | PM never merges to main. Human sign-off required. |
| Final gate | Full suite, migration checks, risk audit. Failure re-enters loop. |
| Evidence | Every claim backed by command output. No trust without proof. |
