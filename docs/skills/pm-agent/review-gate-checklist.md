# Review Gate Checklist

## Minimum Gate (ALL tiers)

- [ ] Gate 1 — Plan alignment: every acceptance criterion mapped to code
- [ ] Gate 2 — Tests added: `tests_to_add` files exist and pass
- [ ] Gate 3 — Tests run: `tests_to_run` all pass
- [ ] Gate 4 — Lint + typecheck: zero errors from environment commands
- [ ] Gate 5 — No orphan TODOs: all TODO/FIXME have follow-up tasks
- [ ] Gate 6 — Review note: summary + risks + rollback present

## CRITICAL Tier Review

All minimum gates PLUS:
- [ ] Code reviewer sub-agent: full diff against design doc — approved
- [ ] All impacted test suites pass (not just task tests)
- [ ] Security: no secrets, no injection, no unvalidated input
- [ ] Data integrity: migrations reversible (if applicable)
- [ ] Breaking changes flagged in release notes artifact

## NORMAL Tier Review

All minimum gates PLUS:
- [ ] Code reviewer sub-agent: changed files + plan alignment — approved
- [ ] Targeted test suites for affected module pass
- [ ] No obvious anti-patterns in changed code

## LOW Tier Review

All minimum gates PLUS:
- [ ] PM reviewed diff: changes match task scope
- [ ] No schema/API/security changes (if found — escalate to NORMAL)

## Verification Matrix

| Check | CRITICAL | NORMAL | LOW |
|-------|----------|--------|-----|
| Full impacted tests | Yes | No | No |
| Targeted module tests | Yes | Yes | No |
| Security scan | Yes | No | No |
| Code reviewer agent | Yes | Yes | No |
| PM reads diff | Yes | Yes | Yes |
| Breaking change flag | Yes | No | No |
| Migration reversibility | If applicable | No | No |
