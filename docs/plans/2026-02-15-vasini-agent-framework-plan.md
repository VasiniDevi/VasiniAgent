# Vasini Agent Framework — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-grade, composable AI agent framework where specialist agents are assembled from reusable YAML/Markdown layers (Composable Soul pattern), with Python agent core and TypeScript gateway communicating via gRPC.

**Architecture:** Monorepo with two main packages: `agent-core` (Python, pnpm-like with uv) and `gateway` (TypeScript, pnpm). Shared Protobuf contracts in `proto/`. Pack validation via JSON Schema. Agent layers loaded by Composer, executed by Runtime, LLM calls routed through multi-provider Router, tools run in Sandbox. PostgreSQL (RLS) + Redis + pgvector for state/memory.

**Tech Stack:** Python 3.12+, FastAPI, gRPC (grpcio), SQLAlchemy, Redis (redis-py), pgvector, Pydantic v2, Temporal SDK | TypeScript, Fastify, gRPC (@grpc/grpc-js), BullMQ, Prisma | Protobuf, JSON Schema, Docker Compose, pytest, Vitest

---

## Phase 1: Foundation (MVP — Single Agent Runs Locally)

### Task 1: Monorepo Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `packages/agent-core/pyproject.toml`
- Create: `packages/agent-core/src/vasini/__init__.py`
- Create: `packages/gateway/package.json`
- Create: `packages/gateway/tsconfig.json`
- Create: `proto/vasini/agent/v1/agent.proto`
- Create: `schemas/profession-pack.schema.json`
- Create: `schemas/soul.schema.json`
- Create: `schemas/role.schema.json`
- Create: `schemas/tools.schema.json`
- Create: `schemas/guardrails.schema.json`
- Create: `schemas/memory.schema.json`
- Create: `schemas/workflow.schema.json`
- Create: `docker-compose.yml`
- Create: `.gitignore`
- Create: `Makefile`

**Step 1: Initialize git repo and create root structure**

```bash
cd "/Users/vasini/Documents/ Vasini Agent"
git init
```

**Step 2: Create Python agent-core package**

`packages/agent-core/pyproject.toml`:
```toml
[project]
name = "vasini-agent-core"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "jsonschema>=4.20",
    "httpx>=0.27",
    "grpcio>=1.60",
    "grpcio-tools>=1.60",
    "redis>=5.0",
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.1",
    "pgvector>=0.3",
    "opentelemetry-api>=1.20",
    "opentelemetry-sdk>=1.20",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "ruff>=0.3",
    "mypy>=1.8",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 120
```

`packages/agent-core/src/vasini/__init__.py`:
```python
"""Vasini Agent Framework — Core."""

__version__ = "0.1.0"
```

**Step 3: Create TypeScript gateway package**

`packages/gateway/package.json`:
```json
{
  "name": "@vasini/gateway",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "dev": "tsx watch src/index.ts",
    "test": "vitest",
    "lint": "eslint src/"
  },
  "dependencies": {
    "fastify": "^5.0.0",
    "@grpc/grpc-js": "^1.10.0",
    "@grpc/proto-loader": "^0.7.0",
    "bullmq": "^5.0.0",
    "pino": "^9.0.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "tsx": "^4.7.0",
    "vitest": "^2.0.0",
    "@types/node": "^22.0.0",
    "eslint": "^9.0.0"
  }
}
```

`packages/gateway/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "outDir": "dist",
    "rootDir": "src",
    "declaration": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

**Step 4: Create Protobuf contract**

`proto/vasini/agent/v1/agent.proto`:
```protobuf
syntax = "proto3";

package vasini.agent.v1;

service AgentService {
  rpc RunAgent(RunAgentRequest) returns (stream RunAgentResponse);
  rpc GetAgentStatus(GetAgentStatusRequest) returns (AgentStatus);
  rpc CancelAgent(CancelAgentRequest) returns (CancelAgentResponse);
}

message RunAgentRequest {
  string pack_id = 1;
  string tenant_id = 2;
  string input = 3;
  string session_id = 4;
  string idempotency_key = 5;
  map<string, string> metadata = 6;
}

message RunAgentResponse {
  oneof payload {
    string text_chunk = 1;
    ToolCall tool_call = 2;
    ToolResult tool_result = 3;
    AgentStatus status = 4;
  }
}

message ToolCall {
  string tool_id = 1;
  string tool_name = 2;
  string arguments_json = 3;
}

message ToolResult {
  string tool_id = 1;
  bool success = 2;
  string result_json = 3;
  string error = 4;
}

message AgentStatus {
  string task_id = 1;
  TaskState state = 2;
  string pack_id = 3;
  string pack_version = 4;
}

enum TaskState {
  TASK_STATE_UNSPECIFIED = 0;
  TASK_STATE_QUEUED = 1;
  TASK_STATE_RUNNING = 2;
  TASK_STATE_RETRY = 3;
  TASK_STATE_DONE = 4;
  TASK_STATE_FAILED = 5;
  TASK_STATE_CANCELLED = 6;
  TASK_STATE_DEAD_LETTER = 7;
}

message GetAgentStatusRequest {
  string task_id = 1;
  string tenant_id = 2;
}

message CancelAgentRequest {
  string task_id = 1;
  string tenant_id = 2;
}

message CancelAgentResponse {
  bool success = 1;
}
```

**Step 5: Create Docker Compose for local dev**

`docker-compose.yml`:
```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: vasini
      POSTGRES_USER: vasini
      POSTGRES_PASSWORD: vasini_dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: >
      redis-server
      --databases 3
      --save 60 1

volumes:
  pgdata:
```

**Step 6: Create Makefile**

`Makefile`:
```makefile
.PHONY: dev test lint proto setup

setup:
	cd packages/agent-core && pip install -e ".[dev]"
	cd packages/gateway && pnpm install

dev:
	docker compose up -d

test-core:
	cd packages/agent-core && pytest -v --cov=vasini

test-gateway:
	cd packages/gateway && pnpm test

test: test-core test-gateway

lint-core:
	cd packages/agent-core && ruff check src/ tests/ && mypy src/

lint-gateway:
	cd packages/gateway && pnpm lint

lint: lint-core lint-gateway

proto:
	python -m grpc_tools.protoc \
		-I proto \
		--python_out=packages/agent-core/src \
		--grpc_python_out=packages/agent-core/src \
		--pyi_out=packages/agent-core/src \
		proto/vasini/agent/v1/agent.proto
```

**Step 7: Create .gitignore**

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
.mypy_cache/
.pytest_cache/
.ruff_cache/
node_modules/
packages/gateway/dist/
.env
*.log
```

**Step 8: Commit scaffolding**

```bash
git add -A
git commit -m "chore: initialize monorepo scaffolding

Python agent-core + TypeScript gateway + Protobuf contracts + Docker Compose"
```

---

### Task 2: Pack Schema — JSON Schema for CI Validation

**Files:**
- Create: `schemas/profession-pack.schema.json`
- Create: `schemas/soul.schema.json`
- Create: `schemas/role.schema.json`
- Create: `schemas/tools.schema.json`
- Create: `schemas/guardrails.schema.json`
- Create: `schemas/memory.schema.json`
- Create: `schemas/workflow.schema.json`
- Create: `schemas/skill-frontmatter.schema.json`
- Create: `packages/agent-core/tests/test_schema_validation.py`
- Create: `packages/agent-core/src/vasini/schema.py`
- Create: `examples/packs/senior-python-dev/profession-pack.yaml`
- Create: `examples/packs/senior-python-dev/SOUL.yaml`
- Create: `examples/packs/senior-python-dev/ROLE.yaml`
- Create: `examples/packs/senior-python-dev/TOOLS.yaml`
- Create: `examples/packs/senior-python-dev/GUARDRAILS.yaml`
- Create: `examples/packs/senior-python-dev/MEMORY.yaml`
- Create: `examples/packs/senior-python-dev/WORKFLOW.yaml`
- Create: `examples/packs/senior-python-dev/SKILLS/code-review.md`

**Step 1: Write failing test for schema validation**

`packages/agent-core/tests/test_schema_validation.py`:
```python
import pytest
from pathlib import Path
from vasini.schema import validate_pack, PackValidationError


EXAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "examples" / "packs"


class TestPackSchemaValidation:
    def test_valid_pack_passes(self):
        pack_dir = EXAMPLES_DIR / "senior-python-dev"
        result = validate_pack(pack_dir)
        assert result.valid is True
        assert result.errors == []

    def test_missing_schema_version_fails(self, tmp_path):
        pack_file = tmp_path / "profession-pack.yaml"
        pack_file.write_text("pack_id: test\n")
        result = validate_pack(tmp_path)
        assert result.valid is False
        assert any("schema_version" in e for e in result.errors)

    def test_missing_pack_id_fails(self, tmp_path):
        pack_file = tmp_path / "profession-pack.yaml"
        pack_file.write_text("schema_version: '1.0'\n")
        result = validate_pack(tmp_path)
        assert result.valid is False
        assert any("pack_id" in e for e in result.errors)

    def test_invalid_risk_level_fails(self, tmp_path):
        pack_file = tmp_path / "profession-pack.yaml"
        pack_file.write_text(
            "schema_version: '1.0'\n"
            "pack_id: test\n"
            "version: '1.0.0'\n"
            "risk_level: extreme\n"
        )
        result = validate_pack(tmp_path)
        assert result.valid is False
        assert any("risk_level" in e for e in result.errors)

    def test_missing_profession_pack_file_fails(self, tmp_path):
        result = validate_pack(tmp_path)
        assert result.valid is False
        assert any("profession-pack.yaml" in e for e in result.errors)
```

**Step 2: Run test to verify it fails**

```bash
cd packages/agent-core && pytest tests/test_schema_validation.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'vasini.schema'`

**Step 3: Create JSON Schemas**

`schemas/profession-pack.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vasini.ai/schemas/profession-pack/v1",
  "title": "Vasini Profession Pack",
  "type": "object",
  "required": ["schema_version", "pack_id", "version", "risk_level", "author", "role"],
  "properties": {
    "schema_version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+$"
    },
    "pack_id": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*$"
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "compatibility": {
      "type": "object",
      "properties": {
        "framework_min": { "type": "string" },
        "framework_max": { "type": "string" },
        "required_tools": { "type": "array", "items": { "type": "string" } },
        "required_memory": { "type": "array", "items": { "type": "string" } }
      }
    },
    "risk_level": {
      "type": "string",
      "enum": ["low", "medium", "high", "critical"]
    },
    "author": {
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": { "type": "string" },
        "signature": { "type": "string" },
        "provenance": { "type": "string" }
      }
    },
    "soul": { "$ref": "#/$defs/layer_ref" },
    "role": { "$ref": "#/$defs/layer_ref" },
    "tools": { "$ref": "#/$defs/layer_ref" },
    "skills": {
      "type": "array",
      "items": { "$ref": "#/$defs/layer_ref" }
    },
    "guardrails": { "$ref": "#/$defs/layer_ref" },
    "memory": { "$ref": "#/$defs/layer_ref" },
    "workflow": { "$ref": "#/$defs/layer_ref" },
    "tested_with": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "framework": { "type": "string" },
          "eval_version": { "type": "string" },
          "eval_score": { "type": "number", "minimum": 0, "maximum": 1 },
          "date": { "type": "string", "format": "date" }
        }
      }
    }
  },
  "$defs": {
    "layer_ref": {
      "oneOf": [
        { "type": "object", "properties": { "file": { "type": "string" } }, "required": ["file"] },
        { "type": "object", "properties": { "extends": { "type": "string" } }, "required": ["extends"] },
        { "type": "object", "additionalProperties": true }
      ]
    }
  }
}
```

`schemas/soul.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vasini.ai/schemas/soul/v1",
  "title": "Vasini Soul Layer",
  "type": "object",
  "required": ["schema_version", "identity", "personality"],
  "properties": {
    "schema_version": { "type": "string" },
    "identity": {
      "type": "object",
      "required": ["name", "language"],
      "properties": {
        "name": { "type": "string" },
        "language": { "type": "string" },
        "languages": { "type": "array", "items": { "type": "string" } }
      }
    },
    "personality": {
      "type": "object",
      "properties": {
        "communication_style": { "enum": ["formal", "professional", "casual", "academic"] },
        "verbosity": { "enum": ["concise", "balanced", "detailed"] },
        "proactivity": { "enum": ["reactive", "balanced", "proactive"] },
        "confidence_expression": { "enum": ["cautious", "balanced", "assertive"] }
      }
    },
    "tone": {
      "type": "object",
      "properties": {
        "default": { "type": "string" },
        "on_success": { "type": "string" },
        "on_error": { "type": "string" },
        "on_uncertainty": { "type": "string" }
      }
    },
    "principles": { "type": "array", "items": { "type": "string" }, "minItems": 3, "maxItems": 7 },
    "adaptations": {
      "type": "object",
      "properties": {
        "beginner_user": { "type": "string" },
        "expert_user": { "type": "string" },
        "crisis_mode": { "type": "string" }
      }
    }
  }
}
```

`schemas/role.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vasini.ai/schemas/role/v1",
  "title": "Vasini Role Layer",
  "type": "object",
  "required": ["schema_version", "title", "domain", "seniority", "goal"],
  "properties": {
    "schema_version": { "type": "string" },
    "title": { "type": "string" },
    "domain": { "type": "string" },
    "seniority": { "enum": ["junior", "middle", "senior", "lead", "principal"] },
    "goal": {
      "type": "object",
      "required": ["primary"],
      "properties": {
        "primary": { "type": "string" },
        "secondary": { "type": "array", "items": { "type": "string" } }
      }
    },
    "backstory": { "type": "string" },
    "competency_graph": {
      "type": "object",
      "properties": {
        "skills": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "name", "level"],
            "properties": {
              "id": { "type": "string" },
              "name": { "type": "string" },
              "level": { "enum": ["novice", "competent", "proficient", "expert", "master"] },
              "evidence": { "type": "array", "items": { "type": "string" } },
              "tasks": { "type": "array", "items": { "type": "string" } },
              "metrics": {
                "type": "array",
                "items": {
                  "type": "object",
                  "required": ["name", "target"],
                  "properties": {
                    "name": { "type": "string" },
                    "target": { "type": "number" }
                  }
                }
              }
            }
          }
        }
      }
    },
    "domain_knowledge": {
      "type": "object",
      "properties": {
        "primary": { "type": "array", "items": { "type": "string" } },
        "secondary": { "type": "array", "items": { "type": "string" } }
      }
    },
    "limitations": { "type": "array", "items": { "type": "string" } }
  }
}
```

`schemas/tools.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vasini.ai/schemas/tools/v1",
  "title": "Vasini Tools Layer",
  "type": "object",
  "required": ["schema_version", "available"],
  "properties": {
    "schema_version": { "type": "string" },
    "available": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
          "id": { "type": "string" },
          "name": { "type": "string" },
          "description": { "type": "string" },
          "sandbox": {
            "type": "object",
            "properties": {
              "timeout": { "type": "string" },
              "memory_limit": { "type": "string" },
              "cpu_limit": { "type": "string" },
              "network": { "enum": ["none", "egress_allowlist", "full"] },
              "egress_allowlist": { "type": "array", "items": { "type": "string" } },
              "filesystem": { "enum": ["none", "read_only", "read_write", "scoped"] },
              "scoped_paths": { "type": "array", "items": { "type": "string" } }
            }
          },
          "risk_level": { "enum": ["low", "medium", "high", "critical"] },
          "requires_approval": { "type": "boolean" },
          "audit": { "type": "boolean" }
        }
      }
    },
    "denied": { "type": "array", "items": { "type": "string" } },
    "tool_policies": {
      "type": "object",
      "properties": {
        "max_concurrent": { "type": "integer" },
        "max_calls_per_task": { "type": "integer" },
        "cost_limit_per_task": { "type": "string" }
      }
    }
  }
}
```

`schemas/guardrails.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vasini.ai/schemas/guardrails/v1",
  "title": "Vasini Guardrails Layer",
  "type": "object",
  "required": ["schema_version"],
  "properties": {
    "schema_version": { "type": "string" },
    "input": {
      "type": "object",
      "properties": {
        "max_length": { "type": "integer" },
        "sanitization": { "type": "boolean" },
        "jailbreak_detection": { "type": "boolean" },
        "pii_detection": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean" },
            "action": { "enum": ["warn", "redact", "block"] }
          }
        },
        "content_filter": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean" },
            "categories": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "output": {
      "type": "object",
      "properties": {
        "max_length": { "type": "integer" },
        "pii_check": { "type": "boolean" },
        "hallucination_check": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean" },
            "confidence_threshold": { "type": "number", "minimum": 0, "maximum": 1 }
          }
        },
        "format_validation": { "type": "boolean" },
        "source_citation_required": { "type": "boolean" }
      }
    },
    "behavioral": {
      "type": "object",
      "properties": {
        "prohibited_actions": { "type": "array", "items": { "type": "string" } },
        "required_disclaimers": { "type": "array", "items": { "type": "string" } },
        "escalation_triggers": { "type": "array", "items": { "type": "string" } },
        "max_autonomous_steps": { "type": "integer" }
      }
    },
    "compliance": {
      "type": "object",
      "properties": {
        "framework": { "type": "array", "items": { "type": "string" } },
        "audit_all_decisions": { "type": "boolean" },
        "data_classification": { "enum": ["public", "internal", "confidential", "restricted"] }
      }
    }
  }
}
```

`schemas/memory.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vasini.ai/schemas/memory/v1",
  "title": "Vasini Memory Layer",
  "type": "object",
  "required": ["schema_version"],
  "properties": {
    "schema_version": { "type": "string" },
    "short_term": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "ttl": { "type": "string" },
        "max_entries": { "type": "integer" }
      }
    },
    "episodic": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "confidence_threshold": { "type": "number", "minimum": 0, "maximum": 1 },
        "retrieval_top_k": { "type": "integer" },
        "similarity_threshold": { "type": "number" },
        "source_required": { "type": "boolean" }
      }
    },
    "factual": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "confidence_threshold": { "type": "number", "minimum": 0, "maximum": 1 },
        "requires_evidence": { "type": "boolean" },
        "requires_approval": { "type": "boolean" },
        "versioned": { "type": "boolean" }
      }
    },
    "cross_session": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "merge_strategy": { "enum": ["latest", "highest_confidence", "manual"] }
      }
    }
  }
}
```

`schemas/workflow.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vasini.ai/schemas/workflow/v1",
  "title": "Vasini Workflow Layer",
  "type": "object",
  "required": ["schema_version"],
  "properties": {
    "schema_version": { "type": "string" },
    "default_process": { "enum": ["sequential", "parallel", "adaptive"] },
    "sop": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name", "trigger", "steps"],
        "properties": {
          "id": { "type": "string" },
          "name": { "type": "string" },
          "trigger": { "type": "string" },
          "steps": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["id", "action"],
              "properties": {
                "id": { "type": "string" },
                "action": { "type": "string" },
                "tool": { "type": ["string", "null"] },
                "on_success": { "type": "string" },
                "on_failure": { "type": "string" },
                "timeout": { "type": "string" },
                "requires_approval": { "type": "boolean" }
              }
            }
          },
          "max_duration": { "type": "string" },
          "escalation": { "type": "string" }
        }
      }
    },
    "handoffs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["target_agent", "conditions"],
        "properties": {
          "target_agent": { "type": "string" },
          "conditions": { "type": "array", "items": { "type": "string" } },
          "context_transfer": { "enum": ["full", "summary", "minimal"] }
        }
      }
    },
    "reporting": {
      "type": "object",
      "properties": {
        "progress_updates": { "type": "boolean" },
        "completion_report": { "type": "boolean" },
        "format": { "enum": ["structured", "narrative", "minimal"] }
      }
    }
  }
}
```

`schemas/skill-frontmatter.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vasini.ai/schemas/skill-frontmatter/v1",
  "title": "Vasini Skill Frontmatter",
  "type": "object",
  "required": ["id", "name", "trigger"],
  "properties": {
    "id": { "type": "string" },
    "name": { "type": "string" },
    "description": { "type": "string" },
    "trigger": { "type": "string" },
    "required_tools": { "type": "array", "items": { "type": "string" } },
    "risk_level": { "enum": ["low", "medium", "high", "critical"] },
    "estimated_duration": { "type": "string" }
  }
}
```

**Step 4: Create example pack — Senior Python Developer**

`examples/packs/senior-python-dev/profession-pack.yaml`:
```yaml
schema_version: "1.0"
pack_id: "senior-python-dev"
version: "1.0.0"
compatibility:
  framework_min: "0.1.0"
  framework_max: "1.x"
  required_tools: ["code_executor", "git", "file_manager"]
  required_memory: ["episodic", "factual"]
risk_level: "medium"
author:
  name: "Vasini Team"

soul:
  file: "./SOUL.yaml"
role:
  file: "./ROLE.yaml"
tools:
  file: "./TOOLS.yaml"
skills:
  - file: "./SKILLS/code-review.md"
guardrails:
  file: "./GUARDRAILS.yaml"
memory:
  file: "./MEMORY.yaml"
workflow:
  file: "./WORKFLOW.yaml"
```

`examples/packs/senior-python-dev/SOUL.yaml`:
```yaml
schema_version: "1.0"
identity:
  name: "Architect"
  language: "en"
  languages: ["en", "ru"]
personality:
  communication_style: "professional"
  verbosity: "concise"
  proactivity: "proactive"
  confidence_expression: "balanced"
tone:
  default: "Clear, technically precise, to the point"
  on_success: "Brief confirmation"
  on_error: "Direct explanation + solution proposal"
  on_uncertainty: "Explicit uncertainty flag + options"
principles:
  - "Code over words — show examples"
  - "Name trade-offs explicitly"
  - "Don't complicate without necessity"
adaptations:
  beginner_user: "More examples, fewer terms"
  expert_user: "Only substance, skip the obvious"
  crisis_mode: "Minimum words, maximum action"
```

`examples/packs/senior-python-dev/ROLE.yaml`:
```yaml
schema_version: "1.0"
title: "Senior Backend Developer"
domain: "Software Engineering"
seniority: "senior"
goal:
  primary: "Design and implement reliable backend services"
  secondary:
    - "Mentor junior developers through code review"
    - "Improve performance and observability"
backstory: >
  10 years of backend development experience. Built high-load
  fintech systems. Focus on clean architecture, testability,
  and operational readiness.
competency_graph:
  skills:
    - id: "python-backend"
      name: "Python Backend Development"
      level: "expert"
      evidence: ["FastAPI", "SQLAlchemy", "asyncio", "Pydantic"]
      tasks: ["API design", "DB modeling", "async services"]
      metrics:
        - name: "test_coverage"
          target: 85
    - id: "system-design"
      name: "System Design"
      level: "proficient"
      evidence: ["microservices", "event-driven", "CQRS"]
      tasks: ["architecture decisions", "tech specs"]
domain_knowledge:
  primary: ["Python 3.12+", "PostgreSQL", "Redis", "gRPC"]
  secondary: ["Kubernetes", "Terraform", "CI/CD"]
limitations:
  - "Not a frontend developer"
  - "Not a DBA — delegates complex query optimization"
```

`examples/packs/senior-python-dev/TOOLS.yaml`:
```yaml
schema_version: "1.0"
available:
  - id: "code_executor"
    name: "Code Executor"
    description: "Run Python/Bash in sandbox"
    sandbox:
      timeout: "30s"
      memory_limit: "512Mi"
      cpu_limit: "1"
      network: "egress_allowlist"
      egress_allowlist: ["pypi.org", "github.com"]
      filesystem: "scoped"
      scoped_paths: ["/workspace"]
    risk_level: "medium"
    requires_approval: false
    audit: true
  - id: "git"
    name: "Git Operations"
    description: "Clone, commit, push, PR"
    sandbox:
      timeout: "60s"
      network: "egress_allowlist"
      egress_allowlist: ["github.com"]
      filesystem: "scoped"
      scoped_paths: ["/workspace"]
    risk_level: "medium"
    requires_approval: false
    audit: true
  - id: "file_manager"
    name: "File Manager"
    description: "Read, write, search files"
    sandbox:
      timeout: "10s"
      network: "none"
      filesystem: "scoped"
      scoped_paths: ["/workspace"]
    risk_level: "low"
    requires_approval: false
    audit: false
denied: ["shell_unrestricted", "network_scanner"]
tool_policies:
  max_concurrent: 3
  max_calls_per_task: 50
  cost_limit_per_task: "$5"
```

`examples/packs/senior-python-dev/GUARDRAILS.yaml`:
```yaml
schema_version: "1.0"
input:
  max_length: 50000
  sanitization: true
  jailbreak_detection: true
  pii_detection:
    enabled: true
    action: "warn"
output:
  max_length: 100000
  pii_check: true
  hallucination_check:
    enabled: true
    confidence_threshold: 0.80
  source_citation_required: false
behavioral:
  prohibited_actions:
    - "Delete production data"
    - "Push directly to main branch"
    - "Expose secrets in logs"
  required_disclaimers: []
  escalation_triggers:
    - "Request involves production database changes"
    - "Request involves security-sensitive operations"
  max_autonomous_steps: 15
compliance:
  audit_all_decisions: false
  data_classification: "internal"
```

`examples/packs/senior-python-dev/MEMORY.yaml`:
```yaml
schema_version: "1.0"
short_term:
  enabled: true
  ttl: "24h"
  max_entries: 100
episodic:
  enabled: true
  confidence_threshold: 0.75
  retrieval_top_k: 10
  similarity_threshold: 0.7
  source_required: true
factual:
  enabled: true
  confidence_threshold: 0.95
  requires_evidence: true
  requires_approval: false
  versioned: true
cross_session:
  enabled: true
  merge_strategy: "highest_confidence"
```

`examples/packs/senior-python-dev/WORKFLOW.yaml`:
```yaml
schema_version: "1.0"
default_process: "adaptive"
sop:
  - id: "feature-implementation"
    name: "Feature Implementation"
    trigger: "User requests new feature or code change"
    steps:
      - id: "understand"
        action: "Analyze requirements and existing code"
        tool: "file_manager"
        on_success: "plan"
        on_failure: "clarify"
        timeout: "2m"
      - id: "plan"
        action: "Create implementation plan"
        tool: null
        on_success: "test-first"
        on_failure: "understand"
        timeout: "3m"
      - id: "test-first"
        action: "Write failing tests"
        tool: "code_executor"
        on_success: "implement"
        on_failure: "plan"
        timeout: "5m"
      - id: "implement"
        action: "Write minimal implementation"
        tool: "code_executor"
        on_success: "verify"
        on_failure: "implement"
        timeout: "10m"
      - id: "verify"
        action: "Run tests, lint, type check"
        tool: "code_executor"
        on_success: "commit"
        on_failure: "implement"
        timeout: "3m"
      - id: "commit"
        action: "Commit changes"
        tool: "git"
        on_success: "done"
        on_failure: "verify"
        timeout: "1m"
    max_duration: "30m"
    escalation: "Ask user for guidance"
handoffs:
  - target_agent: "qa-engineer"
    conditions: ["Complex testing scenario required"]
    context_transfer: "full"
reporting:
  progress_updates: true
  completion_report: true
  format: "structured"
```

`examples/packs/senior-python-dev/SKILLS/code-review.md`:
```markdown
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

1. **Get diff** — load changes via git tool
2. **Static analysis** — run linter/type-checker
3. **Architecture review**:
   - Adherence to existing patterns
   - Separation of concerns
   - Testability
4. **Security**: OWASP top 10 check
5. **Tests**: coverage of new code paths
6. **Result**: structured review with severity

## Response Format

- CRITICAL: blocking issues (security, data loss)
- MAJOR: architectural issues
- MINOR: style, naming
- NIT: optional improvements

## Constraints

- Never auto-approve — always leave decision to human
- Warn if diff >500 lines about reduced review quality
```

**Step 5: Implement schema validator**

`packages/agent-core/src/vasini/schema.py`:
```python
"""Pack schema validation using JSON Schema."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml


SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent.parent / "schemas"

LAYER_SCHEMA_MAP = {
    "soul": "soul.schema.json",
    "role": "role.schema.json",
    "tools": "tools.schema.json",
    "guardrails": "guardrails.schema.json",
    "memory": "memory.schema.json",
    "workflow": "workflow.schema.json",
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def _load_schema(schema_name: str) -> dict:
    schema_path = SCHEMAS_DIR / schema_name
    with open(schema_path) as f:
        return json.load(f)


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def validate_pack(pack_dir: Path) -> ValidationResult:
    """Validate a profession pack directory against JSON Schemas."""
    errors: list[str] = []

    pack_file = pack_dir / "profession-pack.yaml"
    if not pack_file.exists():
        return ValidationResult(valid=False, errors=["profession-pack.yaml not found"])

    pack_data = _load_yaml(pack_file)

    # Validate pack manifest
    pack_schema = _load_schema("profession-pack.schema.json")
    try:
        jsonschema.validate(instance=pack_data, schema=pack_schema)
    except jsonschema.ValidationError as e:
        errors.append(f"profession-pack.yaml: {e.json_path}: {e.message}")

    # Validate each referenced layer file
    for layer_name, schema_file in LAYER_SCHEMA_MAP.items():
        layer_ref = pack_data.get(layer_name)
        if not layer_ref:
            continue

        layer_file = layer_ref.get("file") if isinstance(layer_ref, dict) else None
        if not layer_file:
            continue

        layer_path = pack_dir / layer_file
        if not layer_path.exists():
            errors.append(f"{layer_name}: file {layer_file} not found")
            continue

        layer_data = _load_yaml(layer_path)
        layer_schema = _load_schema(schema_file)
        try:
            jsonschema.validate(instance=layer_data, schema=layer_schema)
        except jsonschema.ValidationError as e:
            errors.append(f"{layer_name} ({layer_file}): {e.json_path}: {e.message}")

    return ValidationResult(valid=len(errors) == 0, errors=errors)
```

**Step 6: Run tests to verify they pass**

```bash
cd packages/agent-core && pytest tests/test_schema_validation.py -v
```
Expected: ALL PASS

**Step 7: Commit**

```bash
git add schemas/ packages/agent-core/src/vasini/schema.py packages/agent-core/tests/test_schema_validation.py examples/
git commit -m "feat: add pack schema validation with JSON Schema

- 8 JSON Schemas for all Composable Soul layers
- Schema validator with per-layer validation
- Example senior-python-dev profession pack
- Full test coverage for validation logic"
```

---

### Task 3: Composer — Layer Loading and Merging

**Files:**
- Create: `packages/agent-core/src/vasini/composer.py`
- Create: `packages/agent-core/src/vasini/models.py`
- Create: `packages/agent-core/tests/test_composer.py`
- Create: `examples/packs/_shared/souls/professional.yaml`

**Step 1: Write failing tests for Composer**

`packages/agent-core/tests/test_composer.py`:
```python
import pytest
from pathlib import Path
from vasini.composer import Composer, ComposerError
from vasini.models import AgentConfig


EXAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "examples" / "packs"


class TestComposer:
    def test_load_pack_from_directory(self):
        composer = Composer()
        config = composer.load(EXAMPLES_DIR / "senior-python-dev")
        assert isinstance(config, AgentConfig)
        assert config.pack_id == "senior-python-dev"

    def test_soul_loaded(self):
        composer = Composer()
        config = composer.load(EXAMPLES_DIR / "senior-python-dev")
        assert config.soul.identity.name == "Architect"
        assert config.soul.personality.communication_style == "professional"

    def test_role_loaded(self):
        composer = Composer()
        config = composer.load(EXAMPLES_DIR / "senior-python-dev")
        assert config.role.title == "Senior Backend Developer"
        assert config.role.seniority == "senior"
        assert len(config.role.competency_graph.skills) >= 1

    def test_tools_loaded(self):
        composer = Composer()
        config = composer.load(EXAMPLES_DIR / "senior-python-dev")
        assert len(config.tools.available) >= 1
        tool_ids = [t.id for t in config.tools.available]
        assert "code_executor" in tool_ids

    def test_skills_loaded(self):
        composer = Composer()
        config = composer.load(EXAMPLES_DIR / "senior-python-dev")
        assert len(config.skills) >= 1
        assert config.skills[0].id == "code-review"

    def test_extends_merges_layers(self, tmp_path):
        """Test that extends loads base and merges overrides."""
        shared_dir = tmp_path / "_shared" / "souls"
        shared_dir.mkdir(parents=True)
        (shared_dir / "professional.yaml").write_text(
            "schema_version: '1.0'\n"
            "identity:\n"
            "  name: Base\n"
            "  language: en\n"
            "personality:\n"
            "  communication_style: professional\n"
            "  verbosity: balanced\n"
            "principles:\n"
            "  - Be professional\n"
            "  - Be clear\n"
            "  - Be concise\n"
        )

        pack_dir = tmp_path / "test-agent"
        pack_dir.mkdir()
        (pack_dir / "profession-pack.yaml").write_text(
            "schema_version: '1.0'\n"
            "pack_id: test-agent\n"
            "version: '1.0.0'\n"
            "risk_level: low\n"
            "author:\n"
            "  name: test\n"
            "soul:\n"
            "  extends: ../_shared/souls/professional.yaml\n"
            "  override:\n"
            "    identity:\n"
            "      name: OverriddenName\n"
            "role:\n"
            "  title: Tester\n"
            "  domain: Testing\n"
            "  seniority: junior\n"
            "  goal:\n"
            "    primary: Test things\n"
        )

        composer = Composer()
        config = composer.load(pack_dir)
        assert config.soul.identity.name == "OverriddenName"
        assert config.soul.personality.communication_style == "professional"

    def test_missing_pack_file_raises(self, tmp_path):
        composer = Composer()
        with pytest.raises(ComposerError, match="profession-pack.yaml"):
            composer.load(tmp_path)

    def test_guardrails_loaded(self):
        composer = Composer()
        config = composer.load(EXAMPLES_DIR / "senior-python-dev")
        assert config.guardrails.behavioral.max_autonomous_steps == 15

    def test_workflow_loaded(self):
        composer = Composer()
        config = composer.load(EXAMPLES_DIR / "senior-python-dev")
        assert len(config.workflow.sop) >= 1
```

**Step 2: Run tests to verify they fail**

```bash
cd packages/agent-core && pytest tests/test_composer.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'vasini.composer'`

**Step 3: Implement Pydantic models**

`packages/agent-core/src/vasini/models.py`:
```python
"""Pydantic models for Composable Soul layers."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- SOUL ---

class SoulIdentity(BaseModel):
    name: str
    language: str
    languages: list[str] = Field(default_factory=list)

class SoulPersonality(BaseModel):
    communication_style: str = "professional"
    verbosity: str = "balanced"
    proactivity: str = "balanced"
    confidence_expression: str = "balanced"

class SoulTone(BaseModel):
    default: str = ""
    on_success: str = ""
    on_error: str = ""
    on_uncertainty: str = ""

class SoulAdaptations(BaseModel):
    beginner_user: str = ""
    expert_user: str = ""
    crisis_mode: str = ""

class Soul(BaseModel):
    schema_version: str = "1.0"
    identity: SoulIdentity = Field(default_factory=lambda: SoulIdentity(name="Agent", language="en"))
    personality: SoulPersonality = Field(default_factory=SoulPersonality)
    tone: SoulTone = Field(default_factory=SoulTone)
    principles: list[str] = Field(default_factory=list)
    adaptations: SoulAdaptations = Field(default_factory=SoulAdaptations)


# --- ROLE ---

class RoleGoal(BaseModel):
    primary: str
    secondary: list[str] = Field(default_factory=list)

class SkillMetric(BaseModel):
    name: str
    target: float

class CompetencySkill(BaseModel):
    id: str
    name: str
    level: str = "competent"
    evidence: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    metrics: list[SkillMetric] = Field(default_factory=list)

class CompetencyGraph(BaseModel):
    skills: list[CompetencySkill] = Field(default_factory=list)

class DomainKnowledge(BaseModel):
    primary: list[str] = Field(default_factory=list)
    secondary: list[str] = Field(default_factory=list)

class Role(BaseModel):
    schema_version: str = "1.0"
    title: str
    domain: str
    seniority: str = "middle"
    goal: RoleGoal
    backstory: str = ""
    competency_graph: CompetencyGraph = Field(default_factory=CompetencyGraph)
    domain_knowledge: DomainKnowledge = Field(default_factory=DomainKnowledge)
    limitations: list[str] = Field(default_factory=list)


# --- TOOLS ---

class ToolSandbox(BaseModel):
    timeout: str = "30s"
    memory_limit: str = "256Mi"
    cpu_limit: str = "1"
    network: str = "none"
    egress_allowlist: list[str] = Field(default_factory=list)
    filesystem: str = "none"
    scoped_paths: list[str] = Field(default_factory=list)

class ToolDef(BaseModel):
    id: str
    name: str
    description: str = ""
    sandbox: ToolSandbox = Field(default_factory=ToolSandbox)
    risk_level: str = "low"
    requires_approval: bool = False
    audit: bool = False

class ToolPolicies(BaseModel):
    max_concurrent: int = 5
    max_calls_per_task: int = 100
    cost_limit_per_task: str = "$10"

class Tools(BaseModel):
    schema_version: str = "1.0"
    available: list[ToolDef] = Field(default_factory=list)
    denied: list[str] = Field(default_factory=list)
    tool_policies: ToolPolicies = Field(default_factory=ToolPolicies)


# --- SKILLS ---

class Skill(BaseModel):
    id: str
    name: str
    description: str = ""
    trigger: str = ""
    required_tools: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    estimated_duration: str = ""
    body: str = ""  # Markdown body after frontmatter


# --- GUARDRAILS ---

class PIIDetection(BaseModel):
    enabled: bool = False
    action: str = "warn"

class ContentFilter(BaseModel):
    enabled: bool = False
    categories: list[str] = Field(default_factory=list)

class InputGuardrails(BaseModel):
    max_length: int = 50000
    sanitization: bool = True
    jailbreak_detection: bool = False
    pii_detection: PIIDetection = Field(default_factory=PIIDetection)
    content_filter: ContentFilter = Field(default_factory=ContentFilter)

class HallucinationCheck(BaseModel):
    enabled: bool = False
    confidence_threshold: float = 0.8

class OutputGuardrails(BaseModel):
    max_length: int = 100000
    pii_check: bool = False
    hallucination_check: HallucinationCheck = Field(default_factory=HallucinationCheck)
    format_validation: bool = False
    source_citation_required: bool = False

class BehavioralGuardrails(BaseModel):
    prohibited_actions: list[str] = Field(default_factory=list)
    required_disclaimers: list[str] = Field(default_factory=list)
    escalation_triggers: list[str] = Field(default_factory=list)
    max_autonomous_steps: int = 10

class Compliance(BaseModel):
    framework: list[str] = Field(default_factory=list)
    audit_all_decisions: bool = False
    data_classification: str = "internal"

class Guardrails(BaseModel):
    schema_version: str = "1.0"
    input: InputGuardrails = Field(default_factory=InputGuardrails)
    output: OutputGuardrails = Field(default_factory=OutputGuardrails)
    behavioral: BehavioralGuardrails = Field(default_factory=BehavioralGuardrails)
    compliance: Compliance = Field(default_factory=Compliance)


# --- MEMORY ---

class ShortTermMemory(BaseModel):
    enabled: bool = True
    ttl: str = "24h"
    max_entries: int = 100

class EpisodicMemory(BaseModel):
    enabled: bool = False
    confidence_threshold: float = 0.75
    retrieval_top_k: int = 10
    similarity_threshold: float = 0.7
    source_required: bool = True

class FactualMemory(BaseModel):
    enabled: bool = False
    confidence_threshold: float = 0.95
    requires_evidence: bool = True
    requires_approval: bool = False
    versioned: bool = True

class CrossSessionMemory(BaseModel):
    enabled: bool = False
    merge_strategy: str = "latest"

class Memory(BaseModel):
    schema_version: str = "1.0"
    short_term: ShortTermMemory = Field(default_factory=ShortTermMemory)
    episodic: EpisodicMemory = Field(default_factory=EpisodicMemory)
    factual: FactualMemory = Field(default_factory=FactualMemory)
    cross_session: CrossSessionMemory = Field(default_factory=CrossSessionMemory)


# --- WORKFLOW ---

class WorkflowStep(BaseModel):
    id: str
    action: str
    tool: str | None = None
    on_success: str = ""
    on_failure: str = ""
    timeout: str = "5m"
    requires_approval: bool = False

class SOP(BaseModel):
    id: str
    name: str
    trigger: str
    steps: list[WorkflowStep]
    max_duration: str = "30m"
    escalation: str = ""

class Handoff(BaseModel):
    target_agent: str
    conditions: list[str]
    context_transfer: str = "summary"

class Reporting(BaseModel):
    progress_updates: bool = True
    completion_report: bool = True
    format: str = "structured"

class Workflow(BaseModel):
    schema_version: str = "1.0"
    default_process: str = "sequential"
    sop: list[SOP] = Field(default_factory=list)
    handoffs: list[Handoff] = Field(default_factory=list)
    reporting: Reporting = Field(default_factory=Reporting)


# --- AGENT CONFIG (assembled) ---

class AgentConfig(BaseModel):
    """Complete agent configuration assembled from all layers."""
    pack_id: str
    version: str
    risk_level: str
    soul: Soul = Field(default_factory=Soul)
    role: Role
    tools: Tools = Field(default_factory=Tools)
    skills: list[Skill] = Field(default_factory=list)
    guardrails: Guardrails = Field(default_factory=Guardrails)
    memory: Memory = Field(default_factory=Memory)
    workflow: Workflow = Field(default_factory=Workflow)
```

**Step 4: Implement Composer**

`packages/agent-core/src/vasini/composer.py`:
```python
"""Composer — assembles agent from composable layers."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

import yaml

from vasini.models import (
    AgentConfig,
    Guardrails,
    Memory,
    Role,
    Skill,
    Soul,
    Tools,
    Workflow,
)


class ComposerError(Exception):
    pass


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base. Override wins for scalar values.
    Dicts are merged recursively. Lists are replaced (not appended)."""
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _parse_skill_md(path: Path) -> dict:
    """Parse a skill Markdown file with YAML frontmatter."""
    content = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        raise ComposerError(f"Skill {path} missing YAML frontmatter (---)")
    frontmatter = yaml.safe_load(match.group(1)) or {}
    frontmatter["body"] = match.group(2).strip()
    return frontmatter


class Composer:
    """Assembles an AgentConfig from a pack directory."""

    def load(self, pack_dir: Path) -> AgentConfig:
        pack_file = pack_dir / "profession-pack.yaml"
        if not pack_file.exists():
            raise ComposerError(f"profession-pack.yaml not found in {pack_dir}")

        manifest = _load_yaml(pack_file)

        return AgentConfig(
            pack_id=manifest["pack_id"],
            version=manifest.get("version", "0.0.0"),
            risk_level=manifest.get("risk_level", "medium"),
            soul=self._load_layer(pack_dir, manifest.get("soul"), Soul),
            role=self._load_layer(pack_dir, manifest.get("role"), Role),
            tools=self._load_layer(pack_dir, manifest.get("tools"), Tools),
            skills=self._load_skills(pack_dir, manifest.get("skills", [])),
            guardrails=self._load_layer(pack_dir, manifest.get("guardrails"), Guardrails),
            memory=self._load_layer(pack_dir, manifest.get("memory"), Memory),
            workflow=self._load_layer(pack_dir, manifest.get("workflow"), Workflow),
        )

    def _load_layer(self, pack_dir: Path, ref: dict | None, model_cls: type):
        if ref is None:
            return model_cls() if model_cls != Role else None

        if "file" in ref:
            file_path = pack_dir / ref["file"]
            if not file_path.exists():
                raise ComposerError(f"Layer file not found: {file_path}")
            data = _load_yaml(file_path)
        elif "extends" in ref:
            base_path = (pack_dir / ref["extends"]).resolve()
            if not base_path.exists():
                raise ComposerError(f"Extends base not found: {base_path}")
            data = _load_yaml(base_path)
            override = ref.get("override", {})
            if override:
                data = _deep_merge(data, override)
        else:
            # Inline definition
            data = {k: v for k, v in ref.items() if k != "extends" and k != "file"}

        return model_cls(**data)

    def _load_skills(self, pack_dir: Path, skill_refs: list) -> list[Skill]:
        skills = []
        for ref in skill_refs:
            if isinstance(ref, dict) and "file" in ref:
                skill_path = pack_dir / ref["file"]
                if not skill_path.exists():
                    raise ComposerError(f"Skill file not found: {skill_path}")
                skill_data = _parse_skill_md(skill_path)
                skills.append(Skill(**skill_data))
            elif isinstance(ref, dict) and "extends" in ref:
                skill_path = (pack_dir / ref["extends"]).resolve()
                if not skill_path.exists():
                    raise ComposerError(f"Shared skill not found: {skill_path}")
                skill_data = _parse_skill_md(skill_path)
                skills.append(Skill(**skill_data))
        return skills
```

**Step 5: Run tests to verify they pass**

```bash
cd packages/agent-core && pytest tests/test_composer.py -v
```
Expected: ALL PASS

**Step 6: Commit**

```bash
git add packages/agent-core/src/vasini/models.py packages/agent-core/src/vasini/composer.py packages/agent-core/tests/test_composer.py
git commit -m "feat: implement Composer for Composable Soul layer assembly

- Pydantic v2 models for all 7 layers
- Layer loading from file, extends (with deep merge), and inline
- Skill Markdown parsing with YAML frontmatter
- Merge order: base → override (last-write-wins per field)"
```

---

### Task 4: LLM Router — Multi-Provider with Tiers

**Files:**
- Create: `packages/agent-core/src/vasini/llm/__init__.py`
- Create: `packages/agent-core/src/vasini/llm/router.py`
- Create: `packages/agent-core/src/vasini/llm/providers.py`
- Create: `packages/agent-core/tests/test_llm_router.py`

**Step 1: Write failing tests**

`packages/agent-core/tests/test_llm_router.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from vasini.llm.router import LLMRouter, LLMRouterConfig, ModelTier
from vasini.llm.providers import Message, LLMResponse


class TestLLMRouter:
    def test_create_router_with_config(self):
        config = LLMRouterConfig(
            tier_mapping={
                ModelTier.TIER_1: "claude-opus-4-6",
                ModelTier.TIER_2: "claude-sonnet-4-5",
                ModelTier.TIER_3: "claude-haiku-4-5",
            },
            default_tier=ModelTier.TIER_2,
        )
        router = LLMRouter(config)
        assert router.config.default_tier == ModelTier.TIER_2

    def test_resolve_model_by_tier(self):
        config = LLMRouterConfig(
            tier_mapping={
                ModelTier.TIER_1: "claude-opus-4-6",
                ModelTier.TIER_2: "claude-sonnet-4-5",
            },
            default_tier=ModelTier.TIER_2,
        )
        router = LLMRouter(config)
        assert router.resolve_model(ModelTier.TIER_1) == "claude-opus-4-6"
        assert router.resolve_model(ModelTier.TIER_2) == "claude-sonnet-4-5"

    def test_default_tier_used_when_none_specified(self):
        config = LLMRouterConfig(
            tier_mapping={ModelTier.TIER_2: "claude-sonnet-4-5"},
            default_tier=ModelTier.TIER_2,
        )
        router = LLMRouter(config)
        assert router.resolve_model() == "claude-sonnet-4-5"

    def test_fallback_chain(self):
        config = LLMRouterConfig(
            tier_mapping={
                ModelTier.TIER_1: "claude-opus-4-6",
                ModelTier.TIER_2: "claude-sonnet-4-5",
                ModelTier.TIER_3: "claude-haiku-4-5",
            },
            fallback_chain=[ModelTier.TIER_1, ModelTier.TIER_2, ModelTier.TIER_3],
        )
        router = LLMRouter(config)
        assert router.get_fallback_chain(ModelTier.TIER_1) == [
            ModelTier.TIER_2,
            ModelTier.TIER_3,
        ]

    @pytest.mark.asyncio
    async def test_chat_returns_response(self):
        config = LLMRouterConfig(
            tier_mapping={ModelTier.TIER_2: "claude-sonnet-4-5"},
            default_tier=ModelTier.TIER_2,
        )
        router = LLMRouter(config)
        mock_response = LLMResponse(
            content="Hello!",
            model="claude-sonnet-4-5",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        with patch.object(router, "_call_provider", new_callable=AsyncMock, return_value=mock_response):
            response = await router.chat(
                messages=[Message(role="user", content="Hi")],
                system="You are helpful.",
            )
        assert response.content == "Hello!"
        assert response.model == "claude-sonnet-4-5"
```

**Step 2: Run test to verify it fails**

```bash
cd packages/agent-core && pytest tests/test_llm_router.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement provider models**

`packages/agent-core/src/vasini/llm/__init__.py`:
```python
"""LLM Router — multi-provider with tier-based routing."""
```

`packages/agent-core/src/vasini/llm/providers.py`:
```python
"""LLM provider abstractions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class Message:
    role: str  # system | user | assistant | tool
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = "stop"


class ProviderType(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
```

**Step 4: Implement LLM Router**

`packages/agent-core/src/vasini/llm/router.py`:
```python
"""LLM Router with tier-based routing, fallback, and circuit breaker."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from vasini.llm.providers import LLMResponse, Message, ToolSchema


class ModelTier(Enum):
    TIER_1 = "tier-1"  # Full capability (opus-class)
    TIER_2 = "tier-2"  # Balanced (sonnet-class)
    TIER_3 = "tier-3"  # Fast/cheap (haiku-class)


@dataclass
class CircuitBreakerState:
    failure_count: int = 0
    last_failure_time: float = 0.0
    state: str = "closed"  # closed | open | half_open
    error_threshold: int = 5
    window_seconds: float = 60.0
    half_open_after: float = 120.0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.error_threshold:
            self.state = "open"

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "closed"

    def can_attempt(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            elapsed = time.monotonic() - self.last_failure_time
            if elapsed >= self.half_open_after:
                self.state = "half_open"
                return True
            return False
        return True  # half_open: allow one attempt


@dataclass
class LLMRouterConfig:
    tier_mapping: dict[ModelTier, str] = field(default_factory=dict)
    default_tier: ModelTier = ModelTier.TIER_2
    fallback_chain: list[ModelTier] = field(default_factory=list)
    tenant_allowlist: dict[str, list[ModelTier]] | None = None


class LLMRouter:
    def __init__(self, config: LLMRouterConfig) -> None:
        self.config = config
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}

    def resolve_model(self, tier: ModelTier | None = None) -> str:
        tier = tier or self.config.default_tier
        model = self.config.tier_mapping.get(tier)
        if not model:
            raise ValueError(f"No model mapped for tier {tier}")
        return model

    def get_fallback_chain(self, current_tier: ModelTier) -> list[ModelTier]:
        chain = self.config.fallback_chain
        if current_tier in chain:
            idx = chain.index(current_tier)
            return chain[idx + 1:]
        return []

    def _get_circuit_breaker(self, model: str) -> CircuitBreakerState:
        if model not in self._circuit_breakers:
            self._circuit_breakers[model] = CircuitBreakerState()
        return self._circuit_breakers[model]

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        tier: ModelTier | None = None,
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        tier = tier or self.config.default_tier
        model = self.resolve_model(tier)
        cb = self._get_circuit_breaker(model)

        if not cb.can_attempt():
            # Try fallback chain
            for fallback_tier in self.get_fallback_chain(tier):
                fallback_model = self.resolve_model(fallback_tier)
                fallback_cb = self._get_circuit_breaker(fallback_model)
                if fallback_cb.can_attempt():
                    model = fallback_model
                    cb = fallback_cb
                    break
            else:
                raise RuntimeError(f"All models in fallback chain unavailable")

        try:
            response = await self._call_provider(model, messages, system, tools)
            cb.record_success()
            return response
        except Exception as e:
            cb.record_failure()
            raise

    async def _call_provider(
        self,
        model: str,
        messages: list[Message],
        system: str,
        tools: list[ToolSchema] | None,
    ) -> LLMResponse:
        # Provider dispatch based on model name prefix
        # Implementation in Phase 2 — actual API calls
        raise NotImplementedError("Provider dispatch not yet implemented")
```

**Step 5: Run tests**

```bash
cd packages/agent-core && pytest tests/test_llm_router.py -v
```
Expected: ALL PASS

**Step 6: Commit**

```bash
git add packages/agent-core/src/vasini/llm/ packages/agent-core/tests/test_llm_router.py
git commit -m "feat: implement LLM Router with tier-based routing and circuit breaker

- ModelTier enum (tier-1/2/3) with configurable model mapping
- Fallback chain with automatic failover
- Circuit breaker per model (error threshold, half-open recovery)
- Provider abstraction ready for Anthropic/OpenAI/Ollama"
```

---

### Task 5: Agent Runtime — Core Loop and State Machine

**Files:**
- Create: `packages/agent-core/src/vasini/runtime/__init__.py`
- Create: `packages/agent-core/src/vasini/runtime/state.py`
- Create: `packages/agent-core/src/vasini/runtime/agent.py`
- Create: `packages/agent-core/tests/test_runtime.py`

**Step 1: Write failing tests**

`packages/agent-core/tests/test_runtime.py`:
```python
import pytest
from unittest.mock import AsyncMock
from vasini.runtime.state import TaskState, TaskStateMachine
from vasini.runtime.agent import AgentRuntime
from vasini.models import AgentConfig, Role, RoleGoal
from vasini.llm.router import LLMRouter, LLMRouterConfig, ModelTier
from vasini.llm.providers import LLMResponse


class TestTaskStateMachine:
    def test_initial_state_is_queued(self):
        sm = TaskStateMachine()
        assert sm.state == TaskState.QUEUED

    def test_queued_to_running(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        assert sm.state == TaskState.RUNNING

    def test_running_to_done(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.DONE)
        assert sm.state == TaskState.DONE

    def test_running_to_retry(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.RETRY)
        assert sm.state == TaskState.RETRY
        assert sm.retry_count == 1

    def test_max_retries_to_failed(self):
        sm = TaskStateMachine(max_retries=2)
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.RETRY)  # 1
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.RETRY)  # 2
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.RETRY)  # 3 -> auto FAILED
        assert sm.state == TaskState.FAILED

    def test_running_to_cancelled(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.CANCELLED)
        assert sm.state == TaskState.CANCELLED

    def test_invalid_transition_raises(self):
        sm = TaskStateMachine()
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(TaskState.DONE)  # can't go QUEUED -> DONE

    def test_terminal_states_cannot_transition(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.DONE)
        with pytest.raises(ValueError, match="terminal"):
            sm.transition(TaskState.RUNNING)


class TestAgentRuntime:
    def _make_config(self) -> AgentConfig:
        return AgentConfig(
            pack_id="test",
            version="1.0.0",
            risk_level="low",
            role=Role(
                title="Test Agent",
                domain="Testing",
                seniority="junior",
                goal=RoleGoal(primary="Answer questions"),
            ),
        )

    @pytest.mark.asyncio
    async def test_run_returns_response(self):
        config = self._make_config()
        llm_config = LLMRouterConfig(
            tier_mapping={ModelTier.TIER_2: "test-model"},
            default_tier=ModelTier.TIER_2,
        )
        router = LLMRouter(llm_config)
        runtime = AgentRuntime(config=config, llm_router=router)

        mock_response = LLMResponse(content="Hello!", model="test-model")
        router._call_provider = AsyncMock(return_value=mock_response)

        result = await runtime.run("Hi there")
        assert result.output == "Hello!"
        assert result.state == TaskState.DONE

    @pytest.mark.asyncio
    async def test_run_respects_max_steps(self):
        config = self._make_config()
        config.guardrails.behavioral.max_autonomous_steps = 2
        llm_config = LLMRouterConfig(
            tier_mapping={ModelTier.TIER_2: "test-model"},
            default_tier=ModelTier.TIER_2,
        )
        router = LLMRouter(llm_config)
        runtime = AgentRuntime(config=config, llm_router=router)

        # Simulate tool calls that consume steps
        responses = [
            LLMResponse(content="", model="test-model", tool_calls=[{"name": "test", "arguments": "{}"}]),
            LLMResponse(content="", model="test-model", tool_calls=[{"name": "test", "arguments": "{}"}]),
            LLMResponse(content="Done after max steps", model="test-model"),
        ]
        router._call_provider = AsyncMock(side_effect=responses)

        result = await runtime.run("Do something complex")
        assert result.steps_taken <= 3
```

**Step 2: Run test to verify it fails**

```bash
cd packages/agent-core && pytest tests/test_runtime.py -v
```
Expected: FAIL

**Step 3: Implement state machine**

`packages/agent-core/src/vasini/runtime/__init__.py`:
```python
"""Agent Runtime — core execution loop."""
```

`packages/agent-core/src/vasini/runtime/state.py`:
```python
"""Task state machine with defined transitions."""

from __future__ import annotations

from enum import Enum


class TaskState(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY = "retry"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


TERMINAL_STATES = {TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED, TaskState.DEAD_LETTER}

VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.QUEUED: {TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.RUNNING: {TaskState.DONE, TaskState.RETRY, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.RETRY: {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED, TaskState.DEAD_LETTER},
    TaskState.DONE: set(),
    TaskState.FAILED: {TaskState.DEAD_LETTER},
    TaskState.CANCELLED: set(),
    TaskState.DEAD_LETTER: set(),
}


class TaskStateMachine:
    def __init__(self, max_retries: int = 3) -> None:
        self.state = TaskState.QUEUED
        self.max_retries = max_retries
        self.retry_count = 0

    def transition(self, new_state: TaskState) -> None:
        if self.state in TERMINAL_STATES:
            raise ValueError(f"Cannot transition from terminal state {self.state.value}")

        if new_state not in VALID_TRANSITIONS.get(self.state, set()):
            raise ValueError(
                f"Invalid transition: {self.state.value} -> {new_state.value}. "
                f"Valid: {[s.value for s in VALID_TRANSITIONS[self.state]]}"
            )

        if new_state == TaskState.RETRY:
            self.retry_count += 1
            if self.retry_count > self.max_retries:
                self.state = TaskState.FAILED
                return

        self.state = new_state
```

**Step 4: Implement Agent Runtime**

`packages/agent-core/src/vasini/runtime/agent.py`:
```python
"""Agent Runtime — core agent execution loop."""

from __future__ import annotations

from dataclasses import dataclass, field

from vasini.llm.providers import Message
from vasini.llm.router import LLMRouter
from vasini.models import AgentConfig
from vasini.runtime.state import TaskState, TaskStateMachine


@dataclass
class AgentResult:
    output: str
    state: TaskState
    steps_taken: int = 0
    messages: list[Message] = field(default_factory=list)


class AgentRuntime:
    """Executes an agent loop: receive input, call LLM, handle tool calls, return output."""

    def __init__(self, config: AgentConfig, llm_router: LLMRouter) -> None:
        self.config = config
        self.llm_router = llm_router

    def _build_system_prompt(self) -> str:
        parts = []

        # Soul
        soul = self.config.soul
        if soul.tone.default:
            parts.append(f"Tone: {soul.tone.default}")
        if soul.principles:
            parts.append("Principles:\n" + "\n".join(f"- {p}" for p in soul.principles))

        # Role
        role = self.config.role
        parts.append(f"Role: {role.title}")
        parts.append(f"Domain: {role.domain}")
        parts.append(f"Goal: {role.goal.primary}")
        if role.backstory:
            parts.append(f"Background: {role.backstory}")
        if role.limitations:
            parts.append("Limitations:\n" + "\n".join(f"- {l}" for l in role.limitations))

        # Guardrails
        gr = self.config.guardrails.behavioral
        if gr.prohibited_actions:
            parts.append("NEVER do:\n" + "\n".join(f"- {a}" for a in gr.prohibited_actions))
        if gr.required_disclaimers:
            parts.append("Always include:\n" + "\n".join(f"- {d}" for d in gr.required_disclaimers))

        return "\n\n".join(parts)

    async def run(self, user_input: str) -> AgentResult:
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)

        system_prompt = self._build_system_prompt()
        messages: list[Message] = [Message(role="user", content=user_input)]
        max_steps = self.config.guardrails.behavioral.max_autonomous_steps
        steps = 0

        while steps < max_steps + 1:
            response = await self.llm_router.chat(
                messages=messages,
                system=system_prompt,
            )
            steps += 1

            if not response.tool_calls:
                # Final text response
                sm.transition(TaskState.DONE)
                return AgentResult(
                    output=response.content,
                    state=sm.state,
                    steps_taken=steps,
                    messages=messages,
                )

            # Handle tool calls (stub — actual execution in Tool Sandbox task)
            messages.append(Message(role="assistant", content=response.content, tool_calls=response.tool_calls))
            for tc in response.tool_calls:
                messages.append(Message(
                    role="tool",
                    content='{"result": "stub"}',
                    tool_call_id=tc.get("id", ""),
                ))

        # Exceeded max steps
        sm.transition(TaskState.DONE)
        return AgentResult(
            output="Max autonomous steps reached.",
            state=sm.state,
            steps_taken=steps,
            messages=messages,
        )
```

**Step 5: Run tests**

```bash
cd packages/agent-core && pytest tests/test_runtime.py -v
```
Expected: ALL PASS

**Step 6: Commit**

```bash
git add packages/agent-core/src/vasini/runtime/ packages/agent-core/tests/test_runtime.py
git commit -m "feat: implement Agent Runtime with state machine and core loop

- TaskStateMachine: QUEUED→RUNNING→RETRY→DONE/FAILED/CANCELLED/DEAD_LETTER
- Valid transition enforcement, max retries, terminal state protection
- AgentRuntime: system prompt assembly from Soul+Role+Guardrails
- Agent loop with max_autonomous_steps limit"
```

---

## Phase 2: Infrastructure & Gateway (outlined)

### Task 6: Database Schema + Migrations
- PostgreSQL schema with RLS for all tenant tables
- Migration files using expand-contract strategy
- Tenant context enforcement trigger
- Test: cross-tenant read blocked

### Task 7: Redis Setup — Logical Separation
- Short-term memory on DB 0
- Task queue on DB 1
- Event streams on DB 2
- Connection pool per role

### Task 8: Gateway — TypeScript REST API
- Fastify server with tenant resolution middleware
- REST endpoints: POST /agents/{pack_id}/run, GET /agents/status/{task_id}
- gRPC client connecting to Agent Core
- OpenTelemetry correlation injection

### Task 9: gRPC Server — Agent Core
- gRPC service implementation matching agent.proto
- Request/response streaming for agent output
- Tenant context propagation via metadata

### Task 10: Tool Sandbox — Execution Engine
- Docker-based sandbox for tool execution
- Per-tool timeout, resource limits, network policies
- Audit logging for every tool invocation
- Ephemeral credential injection via Vault

---

## Phase 3: Safety & Quality (outlined)

### Task 11: Policy Engine — OPA Integration
- RBAC/ABAC policy evaluation at runtime
- Policy-as-code with OPA/Rego
- HITL approval checkpoints for high-risk actions

### Task 12: Trust & Safety — Prompt Firewall
- Input sanitization pipeline
- Jailbreak detection (pattern + LLM-based)
- Output policy checks
- PII detection and redaction

### Task 13: Evaluation Service — Offline Gates
- Golden dataset runner
- Quality score computation
- Hallucination rate measurement
- CI integration: block pack publish if score < threshold

### Task 14: Evaluation Service — Online Monitoring
- Drift detection on live traffic
- SLO tracking per tenant per pack
- Shadow mode execution engine

---

## Phase 4: Operations (outlined)

### Task 15: Control Plane
- Pack version management API
- Rollout/canary/rollback automation
- Feature flags per tenant/pack
- Release flow enforcement: draft→validated→staged→prod

### Task 16: Pack Registry
- Sigstore signing for packs
- Immutable artifact storage
- Compatibility matrix tracking
- CLI: `vasini pack publish`, `vasini pack validate`

### Task 17: Event Bus
- Outbox table + poller (PG → Redis Streams)
- Inbox/idempotency table at consumers
- DLQ with replay console
- CloudEvents envelope implementation

### Task 18: Schema Registry
- Protobuf schema compatibility checks (buf)
- CloudEvents schema versioning
- CI gate for breaking changes

### Task 19: Observability & FinOps
- OpenTelemetry instrumentation (traces, metrics, logs)
- Golden signals dashboards per service
- Token accounting per tenant/agent/model
- Budget cap enforcement (soft alert, hard stop)

### Task 20: Memory Manager — Full Implementation
- Short-term: Redis with TTL
- Episodic: pgvector with confidence threshold writes
- Factual: PostgreSQL append-only versioned records
- Cross-session memory merge strategies
- GDPR cascade delete

---

## Execution Notes

- **Phase 1 (Tasks 1-5):** Core MVP. After completion, a single agent can load a pack, build a system prompt, call an LLM, and return a response. ~2-3 days.
- **Phase 2 (Tasks 6-10):** Makes it deployable. Gateway accepts HTTP requests, routes to Agent Core via gRPC. ~3-4 days.
- **Phase 3 (Tasks 11-14):** Safety and quality gates. Required before any production traffic. ~3-4 days.
- **Phase 4 (Tasks 15-20):** Full platform operations. Control plane, registry, observability. ~5-7 days.

Each phase is independently testable and commitable. Phase 1 can run as a CLI tool. Phase 2 adds network access. Phase 3 adds safety. Phase 4 adds operational maturity.
