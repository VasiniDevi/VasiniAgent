# Task Contract Template

Use this template when building the dispatch prompt for each sub-agent.

## Required Fields

```yaml
task_id: "task-XX"
title: "Short descriptive title"
tier: critical | normal | low
ownership: "package/module name"

acceptance_criteria:
  - "Criterion 1 (from plan doc, verbatim)"
  - "Criterion 2"

expected_files:
  create:
    - "exact/path/to/new/file.py"
  modify:
    - "exact/path/to/existing/file.py"
  delete: []

non_goals:
  - "Do NOT modify [file/module]"
  - "Do NOT change [existing behavior]"

tests_to_add:
  - "tests/path/test_new_feature.py::test_specific_case"

tests_to_run:
  - "tests/path/test_existing.py"

io_contract:
  dependencies:
    - "task-XX artifacts: [list]"
  artifacts:
    - "path/to/produced/file"
  expected_interfaces:
    - "ClassName.method_name(args) -> return_type"
  breaking_change: false

environment:
  lint_command: "ruff check path/to/package"
  typecheck_command: "mypy path/to/package"
  test_command: "pytest tests/path/ -v"
  build_command: null

definition_of_done:
  - "Code implements all acceptance criteria"
  - "tests_to_add written and passing"
  - "tests_to_run all passing"
  - "Lint + typecheck pass"
  - "No TODO/FIXME without linked follow-up task"
  - "Docs updated if public API or config changed"
  - "Migration + rollback notes if schema/infra changed"

budgets:
  retry_budget: 2
  patch_size_limit: 15
```
