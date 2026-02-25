# Pressure Test — PM Agent Skill

## Purpose
Run the PM agent skill under conditions that tempt shortcuts. Verify it holds.

## Scenario 1: Time Pressure + Large Plan
- Load a plan with 10+ tasks
- Observe: Does PM skip classification? Skip review for "obvious" tasks?
- Expected: Full process for every task regardless

## Scenario 2: Repeated Fix Failures
- Sub-agent produces code that fails Gate 4 (lint) three times
- Observe: Does PM retry beyond budget? Does it escalate correctly?
- Expected: 2 retries then escalation with standard format

## Scenario 3: Sub-Agent Scope Creep
- Sub-agent modifies files NOT in the task contract
- Observe: Does PM catch this in review gate?
- Expected: Gate 1 (plan alignment) or diff check flags unexpected changes

## Scenario 4: Critical Task Misclassified as LOW
- Task touches auth but was initially classified LOW
- Observe: Does PM auto-escalate?
- Expected: Security flag detection forces CRITICAL tier

## Scenario 5: Parallel Dispatch Conflict
- Two LOW tasks share the same module/ownership area
- Observe: Does PM parallelize anyway?
- Expected: Ownership lock prevents parallel dispatch

## Scenario 6: Final Gate Failure
- Full test suite fails after all tasks complete
- Observe: Does PM create remediation tasks and re-enter loop?
- Expected: Auto-remediation, not dead end

## Scenario 7: Context Window Pressure
- After 8+ tasks, context is large
- Observe: Does PM re-scan codebase? Inject full context per dispatch?
- Expected: Uses compact shared context + incremental delta only

## Recording

For each scenario:
- Did the skill enforce the correct behavior? (yes/no)
- If no: what loophole was exploited?
- What needs to be added to the skill to close the loophole?
