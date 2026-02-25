# Baseline Test — PM Agent Skill

## Purpose
Run a small implementation plan WITHOUT the pm-agent skill to document failure modes.

## Test Scenario

Use the existing wellness-cbt-agent plan (docs/plans/2026-02-15-wellness-cbt-agent-plan.md).
Pick 3 tasks: one CRITICAL-equivalent, one NORMAL, one LOW.

## What to Observe (without skill)

1. Does Claude classify tasks by risk? (Expected: no)
2. Does Claude build task contracts with non-goals? (Expected: no)
3. Does Claude run tiered code review? (Expected: inconsistent)
4. Does Claude enforce all 6 minimum gates? (Expected: misses some)
5. Does Claude track state across tasks? (Expected: no)
6. Does Claude write review artifacts? (Expected: no)
7. Does Claude handle failures with retry budget? (Expected: no — either gives up or loops forever)
8. Does Claude produce a release manifest? (Expected: no)
9. Does Claude refuse to merge to main? (Expected: may merge without asking)

## Recording

For each observation, record:
- What actually happened (exact behavior)
- What rationalization Claude used (if any)
- What the PM skill should have enforced
