# Integration Test — PM Agent Full Loop

## Purpose
Run the PM agent skill end-to-end on a real (small) plan to verify the complete loop works.

## Setup
1. Create a small test plan with 4 tasks:
   - Task 1 (CRITICAL): Add a new API endpoint with auth check
   - Task 2 (NORMAL): Add a handler that uses the endpoint
   - Task 3 (LOW): Update config docs
   - Task 4 (NORMAL): Add integration test (depends on Task 1 + 2)

2. Invoke `/pm-agent` with the test plan

## Verification Checklist

### Phase 1: Orchestrate
- [ ] Plan loaded and parsed correctly
- [ ] Baseline scan completed (one time only)
- [ ] Shared context block built
- [ ] Tasks classified: 1 CRITICAL, 2 NORMAL, 1 LOW
- [ ] Queue built with correct dependency order
- [ ] Announcement printed with task summary

### Phase 2: Dispatch (per task)
- [ ] Task contract built for each task
- [ ] Security flags checked (Task 1 should trigger CRITICAL)
- [ ] Sub-agent received contract + shared context + delta
- [ ] Sub-agent returned structured output
- [ ] Parallel dispatch NOT attempted for Task 1 (CRITICAL)

### Phase 3: Review Gate (per task)
- [ ] All 6 minimum gates checked
- [ ] CRITICAL tier review for Task 1 (full review + security scan)
- [ ] NORMAL tier review for Tasks 2 and 4
- [ ] LOW tier review for Task 3
- [ ] Fix loop triggered if any gate fails (verify retry budget)

### Phase 4: Progress + Next
- [ ] Review artifact written per task
- [ ] Atomic commit per task with correct message format
- [ ] Checkpoint tag after Task 1 (CRITICAL)
- [ ] State updated after each task
- [ ] Anti-starvation: Task 3 (LOW) not starved
- [ ] Progress report printed after 3 tasks
- [ ] Queue empty then Final Release Gate entered

### Final Release Gate
- [ ] Full test suite ran
- [ ] Full lint + typecheck ran
- [ ] Risk audit completed
- [ ] Completeness check passed
- [ ] Release manifest written
- [ ] Handoff summary presented
- [ ] PM did NOT merge to main
