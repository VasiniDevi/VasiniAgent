# PM Agent — Quick Reference

## Tier Classification

| Tier | Triggers | Review Depth |
|------|----------|-------------|
| CRITICAL | auth, billing, schema, migrations, security, public API, infra | Full: code reviewer + all impacted tests + security scan |
| NORMAL | features, handlers, integrations, internal APIs | Targeted: code reviewer + module tests |
| LOW | UI copy, refactors, docs, config, dev tooling | Sanity: PM reads diff directly |

## Minimum Gates (every task)

1. Plan alignment — criteria to code mapping
2. Tests added — new tests written and green
3. Tests run — existing tests still green
4. Lint + typecheck — zero errors
5. No orphan TODOs — all have follow-up tasks
6. Review note — summary + risks + rollback

## Escalation Format

```
ESCALATION
Problem:     [what]
Impact:      [blocked items]
Options:     [2-3 choices]
Recommended: [your judgment]
Blocking:    yes/no
```

## Sub-Agent Return Format

```
FILES_CHANGED:
  created: [list]
  modified: [list]
  deleted: [list]
TEST_RESULTS:
  tests_added: [pass/fail per test]
  tests_run: [pass/fail per test]
  evidence: [key output lines]
LINT_TYPECHECK:
  lint: pass/fail + evidence
  typecheck: pass/fail + evidence
BLOCKERS: [list or "none"]
RISKS: [list or "none"]
SELF_ASSESSMENT: confident | uncertain | blocked
```

## Progress Report Format

```
PROGRESS — [plan-name]
Completed: X/Y tasks
  CRITICAL: a/b  NORMAL: c/d  LOW: e/f
In progress: [task list]
Blocked: [task list + reason]
Unresolved risks: [count — top 3 by severity]
Next: Task [id] — [title] ([tier])
```

## Commit Message Format

```
type(scope): short description

Refs: task-<id>
Review: docs/reviews/<task-id>-review.md
```

## Branch Convention

```
feat/<plan-id>/<task-id>-short-name
```

## Priority Order

```
CRITICAL (serial) > NORMAL > LOW
Within same tier: dependency order then plan document order
Anti-starvation: 1 LOW after every 3 CRITICAL/NORMAL
```
