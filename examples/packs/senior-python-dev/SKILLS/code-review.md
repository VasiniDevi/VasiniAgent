---
id: code-review
name: Code Review
description: Conduct code review focusing on quality and security
trigger: "When asked to review a PR or diff"
required_tools: ["git", "code_executor"]
risk_level: low
estimated_duration: "5-15min"
---

# Code Review

## Procedure

1. **Get diff** -- load changes via git tool
2. **Static analysis** -- run linter/type-checker
3. **Architecture review**: adherence to patterns, separation of concerns, testability
4. **Security**: OWASP top 10 check
5. **Tests**: coverage of new code paths
6. **Result**: structured review with severity

## Response Format

- CRITICAL: blocking issues (security, data loss)
- MAJOR: architectural issues
- MINOR: style, naming
- NIT: optional improvements

## Constraints

- Never auto-approve -- always leave decision to human
- Warn if diff >500 lines about reduced review quality
