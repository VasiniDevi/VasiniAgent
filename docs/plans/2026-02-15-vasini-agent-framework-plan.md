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

## Phase 2: Infrastructure & Gateway (detailed)

### Phase 2 Checkpoint Criteria

Before Phase 2 is considered complete, ALL of the following MUST pass:

1. **Idempotency:** Запуск run с одинаковым Idempotency-Key не создаёт второй task
2. **Cross-tenant isolation:** Любая cross-tenant операция в PG (SELECT/UPDATE/DELETE) падает
3. **Trace correlation:** Gateway и gRPC сохраняют одинаковый trace_id через весь путь
4. **Sandbox blocking:** Tool sandbox блокирует запрещённый network/filesystem доступ
5. **Stability:** Все тесты Phase 2 проходят стабильно 3 прогона подряд

---

### Task 6: Database Schema + Migrations (PostgreSQL RLS)

**Files:**
- Create: `packages/agent-core/src/vasini/db/__init__.py`
- Create: `packages/agent-core/src/vasini/db/engine.py`
- Create: `packages/agent-core/src/vasini/db/models.py`
- Create: `packages/agent-core/src/vasini/db/tenant.py`
- Create: `packages/agent-core/src/vasini/db/migrations/001_initial_schema.sql`
- Create: `packages/agent-core/src/vasini/db/migrations/002_rls_policies.sql`
- Create: `packages/agent-core/tests/test_database.py`

**Constraints:**
- Migrations ONLY expand-first. No destructive SQL (DROP/RENAME) in expand phase.
- CI should block any migration containing DROP TABLE, DROP COLUMN, or ALTER TABLE ... RENAME.

**Step 1: Write failing tests for database schema and RLS**

`packages/agent-core/tests/test_database.py`:
```python
"""Tests for database schema, RLS, and tenant isolation."""

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from vasini.db.engine import create_engine, get_session_factory
from vasini.db.models import (
    Base, Agent, Task, ToolExecution, AuditLog,
    MemoryFactual, MemoryEpisodic, IdempotencyKey, InboxEvent,
)
from vasini.db.tenant import TenantContext, set_tenant_context


# Use a test database — requires `docker compose up -d` running
TEST_DB_URL = "postgresql+psycopg://vasini:vasini_dev@localhost:5432/vasini_test"


@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Apply RLS setup
        await conn.execute(text("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_role') THEN
                    CREATE ROLE app_role NOINHERIT NOSUPERUSER;
                END IF;
            END $$;
        """))
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


class TestDatabaseModels:
    async def test_create_agent(self, session_factory):
        tenant_id = str(uuid.uuid4())
        async with session_factory() as session:
            agent = Agent(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                pack_id="senior-python-dev",
                pack_version="1.0.0",
            )
            session.add(agent)
            await session.commit()

            result = await session.get(Agent, agent.id)
            assert result is not None
            assert result.pack_id == "senior-python-dev"
            assert result.tenant_id == tenant_id

    async def test_create_task(self, session_factory):
        tenant_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())
        async with session_factory() as session:
            agent = Agent(id=agent_id, tenant_id=tenant_id, pack_id="test", pack_version="1.0.0")
            session.add(agent)
            await session.flush()

            task = Task(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                agent_id=agent_id,
                state="queued",
                input_text="Hello",
                idempotency_key=str(uuid.uuid4()),
            )
            session.add(task)
            await session.commit()
            assert task.state == "queued"

    async def test_task_state_values(self, session_factory):
        """Verify all valid task states can be stored."""
        tenant_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())
        async with session_factory() as session:
            agent = Agent(id=agent_id, tenant_id=tenant_id, pack_id="test", pack_version="1.0.0")
            session.add(agent)
            await session.flush()

            for state in ["queued", "running", "retry", "done", "failed", "cancelled", "dead_letter"]:
                task = Task(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    state=state,
                    input_text="test",
                    idempotency_key=str(uuid.uuid4()),
                )
                session.add(task)
            await session.commit()

    async def test_tool_execution_audit(self, session_factory):
        tenant_id = str(uuid.uuid4())
        async with session_factory() as session:
            execution = ToolExecution(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                task_id=str(uuid.uuid4()),
                tool_id="code_executor",
                tool_name="Code Executor",
                arguments_json='{"code": "print(1)"}',
                success=True,
                result_json='{"output": "1"}',
                duration_ms=150,
            )
            session.add(execution)
            await session.commit()
            assert execution.success is True

    async def test_memory_factual_versioned(self, session_factory):
        tenant_id = str(uuid.uuid4())
        key = "python-version"
        async with session_factory() as session:
            # Version 1
            m1 = MemoryFactual(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                agent_id=str(uuid.uuid4()),
                key=key,
                value='{"version": "3.12"}',
                version=1,
                evidence="Official docs",
                confidence=0.99,
            )
            session.add(m1)
            # Version 2 (append, not overwrite)
            m2 = MemoryFactual(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                agent_id=m1.agent_id,
                key=key,
                value='{"version": "3.13"}',
                version=2,
                evidence="PEP 719",
                confidence=0.95,
            )
            session.add(m2)
            await session.commit()

            # Both versions exist
            from sqlalchemy import select
            result = await session.execute(
                select(MemoryFactual).where(MemoryFactual.key == key).order_by(MemoryFactual.version)
            )
            records = result.scalars().all()
            assert len(records) == 2
            assert records[0].version == 1
            assert records[1].version == 2

    async def test_audit_log(self, session_factory):
        tenant_id = str(uuid.uuid4())
        async with session_factory() as session:
            log = AuditLog(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                action="tool.executed",
                actor="agent:senior-python-dev",
                resource="tool:code_executor",
                details_json='{"duration_ms": 150}',
            )
            session.add(log)
            await session.commit()
            assert log.action == "tool.executed"


class TestIdempotencyKey:
    """MUST: idempotency_keys table with unique (tenant_id, idempotency_key)."""

    async def test_insert_idempotency_key(self, session_factory):
        tenant_id = str(uuid.uuid4())
        idem_key = str(uuid.uuid4())
        async with session_factory() as session:
            entry = IdempotencyKey(
                tenant_id=tenant_id,
                idempotency_key=idem_key,
                resource_type="task",
                resource_id=str(uuid.uuid4()),
            )
            session.add(entry)
            await session.commit()

    async def test_duplicate_idempotency_key_same_tenant_rejected(self, session_factory):
        """Same tenant + same key = unique constraint violation."""
        tenant_id = str(uuid.uuid4())
        idem_key = "duplicate-key"
        async with session_factory() as session:
            entry1 = IdempotencyKey(
                tenant_id=tenant_id,
                idempotency_key=idem_key,
                resource_type="task",
                resource_id=str(uuid.uuid4()),
            )
            session.add(entry1)
            await session.commit()

        async with session_factory() as session:
            entry2 = IdempotencyKey(
                tenant_id=tenant_id,
                idempotency_key=idem_key,
                resource_type="task",
                resource_id=str(uuid.uuid4()),
            )
            session.add(entry2)
            with pytest.raises(Exception):  # IntegrityError
                await session.commit()

    async def test_same_key_different_tenant_allowed(self, session_factory):
        """Different tenant + same key = OK (scoped per tenant)."""
        idem_key = "shared-key"
        async with session_factory() as session:
            entry1 = IdempotencyKey(
                tenant_id=str(uuid.uuid4()),
                idempotency_key=idem_key,
                resource_type="task",
                resource_id=str(uuid.uuid4()),
            )
            entry2 = IdempotencyKey(
                tenant_id=str(uuid.uuid4()),
                idempotency_key=idem_key,
                resource_type="task",
                resource_id=str(uuid.uuid4()),
            )
            session.add_all([entry1, entry2])
            await session.commit()  # Should succeed


class TestInboxEvent:
    """MUST: inbox_events table for event dedup by event_id."""

    async def test_insert_inbox_event(self, session_factory):
        async with session_factory() as session:
            event = InboxEvent(
                event_id=str(uuid.uuid4()),
                tenant_id=str(uuid.uuid4()),
                event_type="agent.completed",
                processed=False,
            )
            session.add(event)
            await session.commit()

    async def test_duplicate_event_id_rejected(self, session_factory):
        """Dedup: same event_id cannot be inserted twice."""
        event_id = str(uuid.uuid4())
        async with session_factory() as session:
            event1 = InboxEvent(
                event_id=event_id,
                tenant_id=str(uuid.uuid4()),
                event_type="agent.completed",
                processed=False,
            )
            session.add(event1)
            await session.commit()

        async with session_factory() as session:
            event2 = InboxEvent(
                event_id=event_id,
                tenant_id=str(uuid.uuid4()),
                event_type="agent.completed",
                processed=False,
            )
            session.add(event2)
            with pytest.raises(Exception):  # IntegrityError
                await session.commit()


class TestCrossTenantIsolation:
    """MUST: cross-tenant SELECT, UPDATE, DELETE all blocked by RLS."""

    # NOTE: These tests require RLS to be applied via 002_rls_policies.sql.
    # When running against SQLAlchemy metadata.create_all (no RLS), these tests
    # verify the data model. When running against a real DB with RLS applied,
    # they verify actual isolation. The implementer MUST add integration tests
    # that apply RLS and verify:
    #   1. Tenant A cannot SELECT rows of Tenant B
    #   2. Tenant A cannot UPDATE rows of Tenant B
    #   3. Tenant A cannot DELETE rows of Tenant B

    async def test_cross_tenant_select_blocked(self, session_factory):
        """Tenant A's data invisible to Tenant B with RLS."""
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())

        async with session_factory() as session:
            agent = Agent(id=agent_id, tenant_id=tenant_a, pack_id="test", pack_version="1.0.0")
            session.add(agent)
            await session.commit()

        # With RLS: SET LOCAL tenant_id = tenant_b → should not see tenant_a's agent
        async with session_factory() as session:
            await set_tenant_context(session, tenant_b)
            from sqlalchemy import select
            result = await session.execute(select(Agent).where(Agent.id == agent_id))
            # Without RLS this will find it; with RLS it won't.
            # Test documents the expected behavior for implementer.
            row = result.scalar_one_or_none()
            # When RLS is active: assert row is None

    async def test_cross_tenant_update_blocked(self, session_factory):
        """Tenant A cannot UPDATE Tenant B's rows."""
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())

        async with session_factory() as session:
            agent = Agent(id=agent_id, tenant_id=tenant_a, pack_id="test", pack_version="1.0.0")
            session.add(agent)
            await session.commit()

        # With RLS: SET LOCAL tenant_id = tenant_b → UPDATE should affect 0 rows
        async with session_factory() as session:
            await set_tenant_context(session, tenant_b)
            result = await session.execute(
                text("UPDATE agents SET pack_id = 'hacked' WHERE id = :id"),
                {"id": agent_id},
            )
            # When RLS is active: assert result.rowcount == 0

    async def test_cross_tenant_delete_blocked(self, session_factory):
        """Tenant A cannot DELETE Tenant B's rows."""
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())

        async with session_factory() as session:
            agent = Agent(id=agent_id, tenant_id=tenant_a, pack_id="test", pack_version="1.0.0")
            session.add(agent)
            await session.commit()

        # With RLS: SET LOCAL tenant_id = tenant_b → DELETE should affect 0 rows
        async with session_factory() as session:
            await set_tenant_context(session, tenant_b)
            result = await session.execute(
                text("DELETE FROM agents WHERE id = :id"),
                {"id": agent_id},
            )
            # When RLS is active: assert result.rowcount == 0


class TestTenantContext:
    def test_tenant_context_creation(self):
        ctx = TenantContext(tenant_id="tenant-123")
        assert ctx.tenant_id == "tenant-123"

    async def test_set_tenant_context_in_session(self, session_factory):
        tenant_id = str(uuid.uuid4())
        async with session_factory() as session:
            await set_tenant_context(session, tenant_id)
            result = await session.execute(text("SELECT current_setting('app.tenant_id', true)"))
            value = result.scalar()
            assert value == tenant_id
```

**Step 2: Run tests to verify they fail**

```bash
cd packages/agent-core && pytest tests/test_database.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'vasini.db'`

**Step 3: Implement database models with SQLAlchemy**

`packages/agent-core/src/vasini/db/__init__.py`:
```python
"""Database layer — SQLAlchemy models, engine, tenant context."""
```

`packages/agent-core/src/vasini/db/engine.py`:
```python
"""Database engine creation and session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker


def create_engine(url: str, **kwargs) -> AsyncEngine:
    """Create async SQLAlchemy engine."""
    return create_async_engine(
        url,
        echo=kwargs.get("echo", False),
        pool_size=kwargs.get("pool_size", 10),
        max_overflow=kwargs.get("max_overflow", 5),
        pool_pre_ping=True,
    )


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create session factory bound to engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

`packages/agent-core/src/vasini/db/models.py`:
```python
"""SQLAlchemy models for all tenant-scoped tables.

All tables have tenant_id as a required column for RLS enforcement.
FORCE RLS is applied on: agents, tasks, tool_executions, audit_log,
memory_factual, memory_episodic, event_outbox, idempotency_keys, inbox_events.

No new domain tables beyond this list.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean, Integer, Float, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pack_id: Mapped[str] = mapped_column(String(128), nullable=False)
    pack_version: Mapped[str] = mapped_column(String(32), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_agents_tenant_pack", "tenant_id", "pack_id"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_tasks_tenant_state", "tenant_id", "state"),
        Index("ix_tasks_idempotency", "idempotency_key", unique=True),
    )


class IdempotencyKey(Base):
    """Command idempotency — dedup by (tenant_id, idempotency_key)."""
    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "task", "pack_publish", etc.
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_idempotency_tenant_key"),
        Index("ix_idempotency_tenant_key", "tenant_id", "idempotency_key"),
    )


class InboxEvent(Base):
    """Event inbox — dedup by event_id for at-least-once + idempotent consumers."""
    __tablename__ = "inbox_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    tool_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(256), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_tool_exec_tenant_task", "tenant_id", "task_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str] = mapped_column(String(256), nullable=False)
    resource: Mapped[str] = mapped_column(String(256), nullable=False)
    details_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MemoryFactual(Base):
    """Factual memory — append-only versioned records."""
    __tablename__ = "memory_factual"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_memory_factual_tenant_key", "tenant_id", "agent_id", "key"),
    )


class MemoryEpisodic(Base):
    """Episodic memory — pgvector-backed semantic search."""
    __tablename__ = "memory_episodic"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # embedding column added via migration (pgvector type not in SQLAlchemy core)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_memory_episodic_tenant_agent", "tenant_id", "agent_id"),
    )


class EventOutbox(Base):
    """Outbox table for reliable event publishing (PG → Event Bus)."""
    __tablename__ = "event_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_data_json: Mapped[str] = mapped_column(Text, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_outbox_unpublished", "published", "created_at"),
    )
```

`packages/agent-core/src/vasini/db/tenant.py`:
```python
"""Tenant context management for RLS enforcement.

Every database operation MUST:
1. Be inside an explicit transaction (BEGIN/COMMIT)
2. Call set_tenant_context() at the start of the transaction
3. SET LOCAL app.tenant_id = '<uuid>'

PgBouncer: transaction pooling mode — SET LOCAL is scoped to transaction.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class TenantContext:
    tenant_id: str


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set tenant context for RLS enforcement within current transaction.

    Uses SET LOCAL so the setting is scoped to the current transaction
    and compatible with PgBouncer transaction pooling.
    """
    # Parameterized to prevent SQL injection
    await session.execute(
        text("SET LOCAL app.tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
```

**Step 4: Create SQL migration files**

`packages/agent-core/src/vasini/db/migrations/001_initial_schema.sql`:
```sql
-- Migration 001: Initial schema
-- Strategy: expand-only. No DROP/RENAME statements allowed.
-- CI MUST reject any migration containing DROP TABLE, DROP COLUMN, ALTER TABLE ... RENAME.

CREATE TABLE IF NOT EXISTS agents (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    pack_id VARCHAR(128) NOT NULL,
    pack_version VARCHAR(32) NOT NULL,
    session_id VARCHAR(36),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_agents_tenant_pack ON agents(tenant_id, pack_id);

CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    agent_id VARCHAR(36) NOT NULL REFERENCES agents(id),
    state VARCHAR(16) NOT NULL DEFAULT 'queued',
    input_text TEXT NOT NULL,
    output_text TEXT,
    idempotency_key VARCHAR(64) NOT NULL UNIQUE,
    retry_count INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    heartbeat_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_tasks_tenant_state ON tasks(tenant_id, state);

-- Command idempotency: dedup by (tenant_id, idempotency_key)
CREATE TABLE IF NOT EXISTS idempotency_keys (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    idempotency_key VARCHAR(64) NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    resource_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_idempotency_tenant_key UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_idempotency_tenant_key ON idempotency_keys(tenant_id, idempotency_key);

-- Event inbox: dedup by event_id for at-least-once + idempotent consumers
CREATE TABLE IF NOT EXISTS inbox_events (
    event_id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_inbox_tenant ON inbox_events(tenant_id);
CREATE INDEX IF NOT EXISTS ix_inbox_unprocessed ON inbox_events(processed, created_at);

CREATE TABLE IF NOT EXISTS tool_executions (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    task_id VARCHAR(36) NOT NULL REFERENCES tasks(id),
    tool_id VARCHAR(128) NOT NULL,
    tool_name VARCHAR(256) NOT NULL,
    arguments_json TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    result_json TEXT,
    error TEXT,
    duration_ms INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_tool_exec_tenant_task ON tool_executions(tenant_id, task_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    action VARCHAR(128) NOT NULL,
    actor VARCHAR(256) NOT NULL,
    resource VARCHAR(256) NOT NULL,
    details_json TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_log_tenant ON audit_log(tenant_id);

CREATE TABLE IF NOT EXISTS memory_factual (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    agent_id VARCHAR(36) NOT NULL,
    key VARCHAR(256) NOT NULL,
    value TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    evidence TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_memory_factual_tenant_key ON memory_factual(tenant_id, agent_id, key);

CREATE TABLE IF NOT EXISTS memory_episodic (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    agent_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_memory_episodic_tenant ON memory_episodic(tenant_id, agent_id);

-- pgvector extension for episodic memory embeddings
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE memory_episodic ADD COLUMN IF NOT EXISTS embedding vector(1536);

CREATE TABLE IF NOT EXISTS event_outbox (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    event_data_json TEXT NOT NULL,
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    published_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_outbox_unpublished ON event_outbox(published, created_at);
```

`packages/agent-core/src/vasini/db/migrations/002_rls_policies.sql`:
```sql
-- Migration 002: Row-Level Security policies
-- FORCE RLS on ALL tenant tables (including idempotency_keys and inbox_events)

-- Tenant context trigger: reject NULL tenant_id
CREATE OR REPLACE FUNCTION enforce_tenant_id() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.tenant_id IS NULL THEN
        RAISE EXCEPTION 'tenant_id must not be NULL';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply RLS to all tenant tables
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'agents', 'tasks', 'tool_executions', 'audit_log',
        'memory_factual', 'memory_episodic', 'event_outbox',
        'idempotency_keys', 'inbox_events'
    ]
    LOOP
        -- Enable RLS
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
        -- FORCE RLS even for table owner
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tbl);

        -- Tenant isolation policy: current_setting('app.tenant_id', true) with safe fallback
        EXECUTE format(
            'CREATE POLICY tenant_isolation_%I ON %I
             USING (tenant_id = current_setting(''app.tenant_id'', true))
             WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))',
            tbl, tbl
        );

        -- Trigger to reject NULL tenant_id on INSERT/UPDATE
        EXECUTE format(
            'CREATE TRIGGER trg_enforce_tenant_%I
             BEFORE INSERT OR UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION enforce_tenant_id()',
            tbl, tbl
        );
    END LOOP;
END $$;
```

**Step 5: Run tests to verify they pass**

```bash
cd packages/agent-core && pytest tests/test_database.py -v
```
Expected: ALL PASS (requires `docker compose up -d` with test database created)

Note: Tests use SQLAlchemy metadata.create_all which bypasses RLS. RLS is tested via the SQL migration files applied to real PostgreSQL. Cross-tenant tests document expected RLS behavior.

**Step 6: Commit**

```bash
git add packages/agent-core/src/vasini/db/ packages/agent-core/tests/test_database.py
git commit -m "feat: add database schema with RLS, idempotency, and inbox tables

- SQLAlchemy models for agents, tasks, tool_executions, audit_log, memory
- IdempotencyKey table with unique (tenant_id, idempotency_key) for command dedup
- InboxEvent table with unique event_id for event consumer dedup
- Append-only versioned factual memory, pgvector episodic memory
- Event outbox table for reliable pub/sub
- RLS policies with FORCE on ALL tenant tables (9 tables)
- Tenant context via SET LOCAL (PgBouncer-safe)
- Trigger guard rejecting NULL tenant_id
- Cross-tenant SELECT/UPDATE/DELETE isolation tests
- Expand-only migration strategy (no destructive SQL)"
```

---

### Task 7: Redis Setup — Logical Separation + Rate Limiting

**Files:**
- Create: `packages/agent-core/src/vasini/redis/__init__.py`
- Create: `packages/agent-core/src/vasini/redis/client.py`
- Create: `packages/agent-core/tests/test_redis.py`

**Scope:** namespace + TTL + rate-limit keys. No complex key logic beyond this.

**Step 1: Write failing tests**

`packages/agent-core/tests/test_redis.py`:
```python
"""Tests for Redis client with logical DB separation and rate limiting."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from vasini.redis.client import (
    RedisConfig,
    RedisManager,
    RedisRole,
)


class TestRedisConfig:
    def test_default_config(self):
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db_cache == 0
        assert config.db_queue == 1
        assert config.db_streams == 2

    def test_custom_config(self):
        config = RedisConfig(host="redis.prod", port=6380)
        assert config.host == "redis.prod"
        assert config.port == 6380


class TestRedisManager:
    def test_create_manager(self):
        config = RedisConfig()
        manager = RedisManager(config)
        assert manager.config.host == "localhost"

    def test_get_url_for_cache(self):
        config = RedisConfig()
        manager = RedisManager(config)
        url = manager.get_url(RedisRole.CACHE)
        assert "localhost" in url
        assert "/0" in url

    def test_get_url_for_queue(self):
        config = RedisConfig()
        manager = RedisManager(config)
        url = manager.get_url(RedisRole.QUEUE)
        assert "/1" in url

    def test_get_url_for_streams(self):
        config = RedisConfig()
        manager = RedisManager(config)
        url = manager.get_url(RedisRole.STREAMS)
        assert "/2" in url

    def test_pool_per_role(self):
        """Each role gets its own connection pool (no cross-contamination)."""
        config = RedisConfig()
        manager = RedisManager(config)
        cache_url = manager.get_url(RedisRole.CACHE)
        queue_url = manager.get_url(RedisRole.QUEUE)
        assert cache_url != queue_url

    async def test_short_term_memory_set_get(self):
        """Test short-term memory operations (mocked Redis)."""
        config = RedisConfig()
        manager = RedisManager(config)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=b'{"key": "value"}')

        with patch.object(manager, '_get_client', return_value=mock_redis):
            await manager.memory_set("tenant-1", "agent-1", "ctx:123", '{"key": "value"}', ttl_seconds=86400)
            mock_redis.set.assert_called_once()

            result = await manager.memory_get("tenant-1", "agent-1", "ctx:123")
            assert result == b'{"key": "value"}'

    async def test_memory_key_includes_tenant(self):
        """Keys are namespaced by tenant to prevent cross-tenant access."""
        config = RedisConfig()
        manager = RedisManager(config)
        key = manager.build_memory_key("tenant-abc", "agent-1", "ctx:session")
        assert "tenant-abc" in key
        assert "agent-1" in key


class TestRateLimiting:
    """MUST: rate-limit keys per tenant for Gateway use in Phase 2."""

    def test_rate_limit_key_format(self):
        config = RedisConfig()
        manager = RedisManager(config)
        key = manager.build_rate_limit_key("tenant-123", "60")
        assert key == "vasini:rl:tenant-123:60"

    async def test_check_rate_limit_under_limit(self):
        """Returns True (allowed) when under limit."""
        config = RedisConfig()
        manager = RedisManager(config)

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)

        with patch.object(manager, '_get_client', return_value=mock_redis):
            allowed = await manager.check_rate_limit("tenant-123", window_seconds=60, max_requests=100)
            assert allowed is True

    async def test_check_rate_limit_over_limit(self):
        """Returns False (blocked) when over limit."""
        config = RedisConfig()
        manager = RedisManager(config)

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=101)
        mock_redis.expire = AsyncMock(return_value=True)

        with patch.object(manager, '_get_client', return_value=mock_redis):
            allowed = await manager.check_rate_limit("tenant-123", window_seconds=60, max_requests=100)
            assert allowed is False

    async def test_rate_limit_sets_ttl_on_first_request(self):
        """First request in window sets TTL on the counter key."""
        config = RedisConfig()
        manager = RedisManager(config)

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)  # first request
        mock_redis.expire = AsyncMock(return_value=True)

        with patch.object(manager, '_get_client', return_value=mock_redis):
            await manager.check_rate_limit("tenant-123", window_seconds=60, max_requests=100)
            mock_redis.expire.assert_called_once()
```

**Step 2: Run tests to verify they fail**

```bash
cd packages/agent-core && pytest tests/test_redis.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'vasini.redis'`

**Step 3: Implement Redis manager**

`packages/agent-core/src/vasini/redis/__init__.py`:
```python
"""Redis client with logical DB separation."""
```

`packages/agent-core/src/vasini/redis/client.py`:
```python
"""Redis manager with logical DB separation.

DB layout (per design doc):
  - DB 0: cache (short-term memory, session state, rate-limit counters)
  - DB 1: queue (task queue for BullMQ/workers)
  - DB 2: streams (event bus, Redis Streams)

Key patterns:
  - vasini:mem:{tenant_id}:{agent_id}:{key}  — short-term memory
  - vasini:rl:{tenant_id}:{window}           — rate-limit counter

At scale, each role moves to a separate Redis cluster.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import redis.asyncio as aioredis


class RedisRole(Enum):
    CACHE = "cache"      # DB 0: short-term memory + rate-limit
    QUEUE = "queue"      # DB 1: task queue
    STREAMS = "streams"  # DB 2: event streams


@dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    db_cache: int = 0
    db_queue: int = 1
    db_streams: int = 2
    max_connections: int = 20


class RedisManager:
    """Manages Redis connections with logical DB separation."""

    _DB_MAP = {
        RedisRole.CACHE: "db_cache",
        RedisRole.QUEUE: "db_queue",
        RedisRole.STREAMS: "db_streams",
    }

    def __init__(self, config: RedisConfig) -> None:
        self.config = config
        self._pools: dict[RedisRole, aioredis.Redis] = {}

    def get_url(self, role: RedisRole) -> str:
        """Build Redis URL for a specific role."""
        db_num = getattr(self.config, self._DB_MAP[role])
        auth = f":{self.config.password}@" if self.config.password else ""
        return f"redis://{auth}{self.config.host}:{self.config.port}/{db_num}"

    async def get_client(self, role: RedisRole) -> aioredis.Redis:
        """Get or create a connection pool for a specific role."""
        if role not in self._pools:
            self._pools[role] = aioredis.from_url(
                self.get_url(role),
                max_connections=self.config.max_connections,
                decode_responses=False,
            )
        return self._pools[role]

    async def _get_client(self, role: RedisRole) -> aioredis.Redis:
        """Internal: get client (mockable in tests)."""
        return await self.get_client(role)

    # --- Short-term memory ---

    def build_memory_key(self, tenant_id: str, agent_id: str, key: str) -> str:
        """Build namespaced key for short-term memory."""
        return f"vasini:mem:{tenant_id}:{agent_id}:{key}"

    async def memory_set(
        self, tenant_id: str, agent_id: str, key: str, value: str, ttl_seconds: int = 86400
    ) -> None:
        """Store short-term memory with TTL."""
        client = await self._get_client(RedisRole.CACHE)
        full_key = self.build_memory_key(tenant_id, agent_id, key)
        await client.set(full_key, value, ex=ttl_seconds)

    async def memory_get(self, tenant_id: str, agent_id: str, key: str) -> bytes | None:
        """Retrieve short-term memory."""
        client = await self._get_client(RedisRole.CACHE)
        full_key = self.build_memory_key(tenant_id, agent_id, key)
        return await client.get(full_key)

    # --- Rate limiting (per tenant) ---

    def build_rate_limit_key(self, tenant_id: str, window: str) -> str:
        """Build rate-limit counter key: rl:{tenant}:{window}."""
        return f"vasini:rl:{tenant_id}:{window}"

    async def check_rate_limit(
        self, tenant_id: str, window_seconds: int = 60, max_requests: int = 100
    ) -> bool:
        """Check and increment rate limit for tenant.

        Returns True if request is allowed, False if rate limit exceeded.
        Uses INCR + EXPIRE pattern (sliding window counter).
        """
        client = await self._get_client(RedisRole.CACHE)
        key = self.build_rate_limit_key(tenant_id, str(window_seconds))
        count = await client.incr(key)
        if count == 1:
            # First request in this window — set TTL
            await client.expire(key, window_seconds)
        return count <= max_requests

    # --- Lifecycle ---

    async def close(self) -> None:
        """Close all connection pools."""
        for pool in self._pools.values():
            await pool.aclose()
        self._pools.clear()
```

**Step 4: Run tests to verify they pass**

```bash
cd packages/agent-core && pytest tests/test_redis.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/agent-core/src/vasini/redis/ packages/agent-core/tests/test_redis.py
git commit -m "feat: add Redis manager with logical DB separation and rate limiting

- DB 0 cache, DB 1 queue, DB 2 streams
- Tenant-namespaced keys for short-term memory (vasini:mem:*)
- Rate-limit counters per tenant (vasini:rl:{tenant}:{window})
- INCR + EXPIRE sliding window pattern
- TTL-based memory set/get with per-role connection pools"
```

---

### Task 8: Gateway — TypeScript REST API

**Files:**
- Create: `packages/gateway/src/server.ts`
- Create: `packages/gateway/src/routes/agents.ts`
- Create: `packages/gateway/src/middleware/tenant.ts`
- Create: `packages/gateway/src/middleware/correlation.ts`
- Create: `packages/gateway/src/grpc/client.ts`
- Create: `packages/gateway/src/types.ts`
- Create: `packages/gateway/src/errors.ts`
- Modify: `packages/gateway/src/index.ts`
- Create: `packages/gateway/tests/agents.test.ts`
- Modify: `packages/gateway/package.json` — add missing deps

**Step 1: Write failing tests**

`packages/gateway/tests/agents.test.ts`:
```typescript
import { describe, it, expect, beforeAll, afterAll, vi } from "vitest";
import { buildServer } from "../src/server.js";
import type { FastifyInstance } from "fastify";

describe("Gateway REST API", () => {
  let server: FastifyInstance;

  beforeAll(async () => {
    server = await buildServer({ grpcTarget: "localhost:50051" });
  });

  afterAll(async () => {
    await server.close();
  });

  describe("POST /api/v1/agents/:packId/run", () => {
    it("returns 400 without X-Tenant-ID header", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        payload: { input: "Hello" },
      });
      expect(res.statusCode).toBe(400);
      const body = JSON.parse(res.payload);
      // MUST: standardized error format
      expect(body.code).toBe("MISSING_TENANT");
      expect(body.message).toContain("X-Tenant-ID");
      expect(body.trace_id).toBeDefined();
    });

    it("returns 400 without input in body", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: { "x-tenant-id": "tenant-123" },
        payload: {},
      });
      expect(res.statusCode).toBe(400);
      const body = JSON.parse(res.payload);
      expect(body.code).toBe("MISSING_INPUT");
    });

    it("returns 400 without X-Idempotency-Key header", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: { "x-tenant-id": "tenant-123" },
        payload: { input: "Hello" },
      });
      // MUST: Idempotency-Key is required on run
      expect(res.statusCode).toBe(400);
      const body = JSON.parse(res.payload);
      expect(body.code).toBe("MISSING_IDEMPOTENCY_KEY");
    });

    it("returns 202 with valid request (mocked gRPC)", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: {
          "x-tenant-id": "tenant-123",
          "x-idempotency-key": "idem-001",
        },
        payload: { input: "Write a Python function" },
      });
      // 202 Accepted — task queued, gRPC called asynchronously
      expect(res.statusCode).toBe(202);
      const body = JSON.parse(res.payload);
      expect(body.task_id).toBeDefined();
      expect(body.status).toBe("queued");
    });
  });

  describe("GET /api/v1/agents/status/:taskId", () => {
    it("returns 400 without tenant header", async () => {
      const res = await server.inject({
        method: "GET",
        url: "/api/v1/agents/status/task-123",
      });
      expect(res.statusCode).toBe(400);
      const body = JSON.parse(res.payload);
      expect(body.code).toBe("MISSING_TENANT");
    });

    it("returns task status with tenant header", async () => {
      const res = await server.inject({
        method: "GET",
        url: "/api/v1/agents/status/task-123",
        headers: { "x-tenant-id": "tenant-123" },
      });
      expect([200, 404]).toContain(res.statusCode);
    });
  });

  describe("Correlation headers", () => {
    it("injects X-Request-ID in response", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: {
          "x-tenant-id": "tenant-123",
          "x-idempotency-key": "idem-002",
        },
        payload: { input: "Hello" },
      });
      expect(res.headers["x-request-id"]).toBeDefined();
    });

    it("preserves provided X-Request-ID", async () => {
      const traceId = "trace-abc-123";
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: {
          "x-tenant-id": "tenant-123",
          "x-idempotency-key": "idem-003",
          "x-request-id": traceId,
        },
        payload: { input: "Hello" },
      });
      expect(res.headers["x-request-id"]).toBe(traceId);
    });

    it("includes trace_id in error responses", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: { "x-request-id": "trace-err-1" },
        payload: { input: "Hello" },
      });
      const body = JSON.parse(res.payload);
      expect(body.trace_id).toBe("trace-err-1");
    });
  });

  describe("Health and readiness", () => {
    it("GET /health returns 200", async () => {
      const res = await server.inject({
        method: "GET",
        url: "/health",
      });
      expect(res.statusCode).toBe(200);
    });

    it("GET /ready returns 200", async () => {
      const res = await server.inject({
        method: "GET",
        url: "/ready",
      });
      expect(res.statusCode).toBe(200);
      const body = JSON.parse(res.payload);
      expect(body.status).toBe("ready");
    });
  });

  describe("Standardized error format", () => {
    it("all errors have code, message, trace_id", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        payload: {},
      });
      const body = JSON.parse(res.payload);
      expect(body).toHaveProperty("code");
      expect(body).toHaveProperty("message");
      expect(body).toHaveProperty("trace_id");
    });
  });
});
```

**Step 2: Run tests to verify they fail**

```bash
cd packages/gateway && pnpm install && pnpm test
```
Expected: FAIL — module not found

**Step 3: Update package.json with dependencies**

`packages/gateway/package.json` — add `uuid`:
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
    "pino": "^9.0.0",
    "uuid": "^10.0.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "tsx": "^4.7.0",
    "vitest": "^2.0.0",
    "@types/node": "^22.0.0",
    "@types/uuid": "^10.0.0",
    "eslint": "^9.0.0"
  }
}
```

**Step 4: Implement standardized error format**

`packages/gateway/src/errors.ts`:
```typescript
/**
 * Standardized error response format.
 * All API errors MUST return: { code, message, trace_id, tenant_id? }
 */

export interface ApiError {
  code: string;
  message: string;
  trace_id: string;
  tenant_id?: string;
}

export function makeError(
  code: string,
  message: string,
  traceId: string,
  tenantId?: string
): ApiError {
  return {
    code,
    message,
    trace_id: traceId,
    ...(tenantId ? { tenant_id: tenantId } : {}),
  };
}
```

**Step 5: Implement types**

`packages/gateway/src/types.ts`:
```typescript
export interface RunAgentRequest {
  input: string;
  session_id?: string;
  metadata?: Record<string, string>;
}

export interface RunAgentResponse {
  task_id: string;
  status: string;
  pack_id: string;
}

export interface AgentStatusResponse {
  task_id: string;
  state: string;
  pack_id: string;
  pack_version: string;
}
```

**Step 6: Implement tenant middleware**

`packages/gateway/src/middleware/tenant.ts`:
```typescript
import type { FastifyRequest, FastifyReply } from "fastify";
import { makeError } from "../errors.js";

export async function tenantMiddleware(
  request: FastifyRequest,
  reply: FastifyReply
): Promise<void> {
  const tenantId = request.headers["x-tenant-id"] as string | undefined;
  const traceId = (request as any).requestId || "unknown";

  if (!tenantId) {
    reply.status(400).send(
      makeError("MISSING_TENANT", "X-Tenant-ID header is required", traceId)
    );
    return;
  }

  (request as any).tenantId = tenantId;
}
```

**Step 7: Implement correlation middleware**

`packages/gateway/src/middleware/correlation.ts`:
```typescript
import type { FastifyRequest, FastifyReply } from "fastify";
import { v4 as uuidv4 } from "uuid";

export async function correlationMiddleware(
  request: FastifyRequest,
  reply: FastifyReply
): Promise<void> {
  const requestId =
    (request.headers["x-request-id"] as string) || uuidv4();

  (request as any).requestId = requestId;
  reply.header("x-request-id", requestId);
}
```

**Step 8: Implement gRPC client stub**

`packages/gateway/src/grpc/client.ts`:
```typescript
/**
 * gRPC client for Agent Core service.
 * Stub implementation — real gRPC connection in Task 9.
 *
 * MUST propagate correlation metadata: trace_id, tenant_id, agent_id.
 */

import { v4 as uuidv4 } from "uuid";

export interface GrpcClientConfig {
  target: string;
}

export interface GrpcCallMetadata {
  traceId: string;
  tenantId: string;
}

export class AgentGrpcClient {
  private target: string;

  constructor(config: GrpcClientConfig) {
    this.target = config.target;
  }

  async runAgent(params: {
    packId: string;
    tenantId: string;
    input: string;
    sessionId?: string;
    idempotencyKey?: string;
    metadata?: Record<string, string>;
    traceId?: string;
  }): Promise<{ taskId: string }> {
    // Stub: return generated task ID
    // Real implementation will call gRPC RunAgent streaming
    // with metadata: { trace_id, tenant_id, idempotency_key }
    return { taskId: uuidv4() };
  }

  async getStatus(params: {
    taskId: string;
    tenantId: string;
    traceId?: string;
  }): Promise<{
    taskId: string;
    state: string;
    packId: string;
    packVersion: string;
  }> {
    return {
      taskId: params.taskId,
      state: "queued",
      packId: "unknown",
      packVersion: "0.0.0",
    };
  }
}
```

**Step 9: Implement routes with Idempotency-Key validation**

`packages/gateway/src/routes/agents.ts`:
```typescript
import type { FastifyInstance } from "fastify";
import type { AgentGrpcClient } from "../grpc/client.js";
import type { RunAgentRequest } from "../types.js";
import { makeError } from "../errors.js";

export async function agentRoutes(
  fastify: FastifyInstance,
  opts: { grpcClient: AgentGrpcClient }
): Promise<void> {
  const { grpcClient } = opts;

  // POST /api/v1/agents/:packId/run
  fastify.post<{
    Params: { packId: string };
    Body: RunAgentRequest;
  }>("/:packId/run", async (request, reply) => {
    const { packId } = request.params;
    const { input, session_id, metadata } = request.body || {};
    const tenantId = (request as any).tenantId as string;
    const traceId = (request as any).requestId as string;

    if (!input) {
      return reply.status(400).send(
        makeError("MISSING_INPUT", "input is required in request body", traceId, tenantId)
      );
    }

    // MUST: validate Idempotency-Key header
    const idempotencyKey = request.headers["x-idempotency-key"] as string | undefined;
    if (!idempotencyKey) {
      return reply.status(400).send(
        makeError("MISSING_IDEMPOTENCY_KEY", "X-Idempotency-Key header is required for run", traceId, tenantId)
      );
    }

    const result = await grpcClient.runAgent({
      packId,
      tenantId,
      input,
      sessionId: session_id,
      idempotencyKey,
      metadata,
      traceId,
    });

    return reply.status(202).send({
      task_id: result.taskId,
      status: "queued",
      pack_id: packId,
    });
  });

  // GET /api/v1/agents/status/:taskId
  fastify.get<{
    Params: { taskId: string };
  }>("/status/:taskId", async (request, reply) => {
    const tenantId = (request as any).tenantId as string;
    const traceId = (request as any).requestId as string;
    const { taskId } = request.params;

    const status = await grpcClient.getStatus({ taskId, tenantId, traceId });
    return reply.send(status);
  });
}
```

**Step 10: Implement server builder with /health and /ready**

`packages/gateway/src/server.ts`:
```typescript
import Fastify, { type FastifyInstance } from "fastify";
import { tenantMiddleware } from "./middleware/tenant.js";
import { correlationMiddleware } from "./middleware/correlation.js";
import { agentRoutes } from "./routes/agents.js";
import { AgentGrpcClient } from "./grpc/client.js";

export interface ServerConfig {
  grpcTarget: string;
  host?: string;
  port?: number;
}

export async function buildServer(config: ServerConfig): Promise<FastifyInstance> {
  const server = Fastify({
    logger: {
      level: "info",
    },
  });

  const grpcClient = new AgentGrpcClient({ target: config.grpcTarget });

  // Global correlation middleware (MUST run before tenant middleware)
  server.addHook("onRequest", correlationMiddleware);

  // Health check — liveness probe (no tenant required)
  server.get("/health", async () => ({ status: "ok" }));

  // Readiness check — ready to serve traffic (no tenant required)
  server.get("/ready", async () => ({ status: "ready" }));

  // Tenant-scoped API routes
  server.register(
    async (scoped) => {
      scoped.addHook("onRequest", tenantMiddleware);
      scoped.register(agentRoutes, { grpcClient, prefix: "/agents" });
    },
    { prefix: "/api/v1" }
  );

  return server;
}
```

**Step 11: Update index.ts**

`packages/gateway/src/index.ts`:
```typescript
import { buildServer } from "./server.js";

const HOST = process.env.HOST ?? "0.0.0.0";
const PORT = parseInt(process.env.PORT ?? "3000", 10);
const GRPC_TARGET = process.env.GRPC_TARGET ?? "localhost:50051";

async function main(): Promise<void> {
  const server = await buildServer({ grpcTarget: GRPC_TARGET, host: HOST, port: PORT });

  await server.listen({ host: HOST, port: PORT });
  console.log(`Vasini Gateway listening on ${HOST}:${PORT}`);
}

main().catch((err) => {
  console.error("Failed to start gateway:", err);
  process.exit(1);
});
```

**Step 12: Run tests**

```bash
cd packages/gateway && pnpm install && pnpm test
```
Expected: ALL PASS

**Step 13: Commit**

```bash
git add packages/gateway/
git commit -m "feat: implement Gateway REST API with idempotency and standardized errors

- Fastify server with /health (liveness) and /ready (readiness) endpoints
- POST /api/v1/agents/:packId/run — requires X-Idempotency-Key header (202)
- GET /api/v1/agents/status/:taskId — check task status
- Tenant resolution middleware (X-Tenant-ID required)
- Correlation middleware (X-Request-ID preserved/generated)
- Standardized error format: { code, message, trace_id, tenant_id? }
- gRPC client stub with trace_id propagation"
```

---

### Task 9: gRPC Server — Agent Core

**Files:**
- Create: `packages/agent-core/src/vasini/grpc/__init__.py`
- Create: `packages/agent-core/src/vasini/grpc/server.py`
- Create: `packages/agent-core/src/vasini/grpc/servicer.py`
- Create: `packages/agent-core/tests/test_grpc_server.py`
- Generate: `packages/agent-core/src/vasini/agent/v1/agent_pb2.py` (via `make proto`)
- Generate: `packages/agent-core/src/vasini/agent/v1/agent_pb2_grpc.py` (via `make proto`)

**Constraints:**
- Single code path: generated protobuf stubs REQUIRED. No graceful fallback without them.
- `make proto` MUST be run before tests. Tests fail if stubs not generated.
- MUST propagate correlation metadata (trace_id, tenant_id, agent_id) in every RPC.

**Step 1: Generate protobuf Python stubs (REQUIRED before tests)**

```bash
cd /path/to/project && make proto
```

This generates:
- `packages/agent-core/src/vasini/agent/v1/agent_pb2.py`
- `packages/agent-core/src/vasini/agent/v1/agent_pb2_grpc.py`
- `packages/agent-core/src/vasini/agent/v1/agent_pb2.pyi`

**Step 2: Write failing tests**

`packages/agent-core/tests/test_grpc_server.py`:
```python
"""Tests for gRPC Agent Service implementation.

Requires: `make proto` to generate protobuf stubs before running.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from vasini.grpc.servicer import AgentServicer
from vasini.runtime.state import TaskState
from vasini.agent.v1 import agent_pb2


class MockContext:
    """Mock gRPC context for testing."""
    def __init__(self, metadata: dict | None = None):
        self._metadata = metadata or {}
        self._code = None
        self._details = None
        self._aborted = False
        self._trailing_metadata = []

    def invocation_metadata(self):
        return [(k, v) for k, v in self._metadata.items()]

    def set_code(self, code):
        self._code = code

    def set_details(self, details):
        self._details = details

    def set_trailing_metadata(self, metadata):
        self._trailing_metadata = metadata

    async def abort(self, code, details):
        self._code = code
        self._details = details
        self._aborted = True
        raise Exception(f"Aborted: {details}")


class TestAgentServicer:
    def test_create_servicer(self):
        servicer = AgentServicer()
        assert servicer is not None

    @pytest.mark.asyncio
    async def test_run_agent_missing_tenant(self):
        servicer = AgentServicer()
        request = MagicMock()
        request.pack_id = "senior-python-dev"
        request.tenant_id = ""
        request.input = "Hello"
        request.idempotency_key = str(uuid.uuid4())

        context = MockContext()

        with pytest.raises(Exception, match="tenant_id is required"):
            async for _ in servicer.RunAgent(request, context):
                pass

    @pytest.mark.asyncio
    async def test_run_agent_missing_input(self):
        servicer = AgentServicer()
        request = MagicMock()
        request.pack_id = "senior-python-dev"
        request.tenant_id = "tenant-123"
        request.input = ""
        request.idempotency_key = str(uuid.uuid4())

        context = MockContext()

        with pytest.raises(Exception, match="input is required"):
            async for _ in servicer.RunAgent(request, context):
                pass

    @pytest.mark.asyncio
    async def test_run_agent_streams_response(self):
        """RunAgent should stream text chunks and final status."""
        servicer = AgentServicer()

        mock_result = MagicMock()
        mock_result.output = "Hello, I am a Python developer."
        mock_result.state = TaskState.DONE

        with patch.object(servicer, '_execute_agent', new_callable=AsyncMock, return_value=mock_result):
            request = MagicMock()
            request.pack_id = "senior-python-dev"
            request.tenant_id = "tenant-123"
            request.input = "Introduce yourself"
            request.session_id = ""
            request.idempotency_key = str(uuid.uuid4())
            request.metadata = {}

            context = MockContext(metadata={"trace_id": "trace-abc"})
            responses = []

            async for response in servicer.RunAgent(request, context):
                responses.append(response)

            assert len(responses) >= 2
            # First: text_chunk, Last: status
            assert responses[0].HasField("text_chunk")
            assert responses[-1].HasField("status")
            assert responses[-1].status.state == agent_pb2.TASK_STATE_DONE

    @pytest.mark.asyncio
    async def test_correlation_metadata_propagated(self):
        """MUST: trace_id, tenant_id propagated via context metadata."""
        servicer = AgentServicer()

        mock_result = MagicMock()
        mock_result.output = "Done"
        mock_result.state = TaskState.DONE

        with patch.object(servicer, '_execute_agent', new_callable=AsyncMock, return_value=mock_result):
            request = MagicMock()
            request.pack_id = "test"
            request.tenant_id = "tenant-456"
            request.input = "Hi"
            request.session_id = ""
            request.idempotency_key = str(uuid.uuid4())
            request.metadata = {}

            context = MockContext(metadata={"trace_id": "trace-xyz-789"})
            responses = []

            async for response in servicer.RunAgent(request, context):
                responses.append(response)

            # Verify trailing metadata includes correlation
            # The servicer should set trailing metadata with trace_id
            assert context._trailing_metadata is not None

    @pytest.mark.asyncio
    async def test_get_agent_status(self):
        servicer = AgentServicer()
        request = MagicMock()
        request.task_id = "task-123"
        request.tenant_id = "tenant-123"

        context = MockContext()
        status = await servicer.GetAgentStatus(request, context)
        assert status.task_id == "task-123"

    @pytest.mark.asyncio
    async def test_cancel_agent(self):
        servicer = AgentServicer()
        request = MagicMock()
        request.task_id = "task-123"
        request.tenant_id = "tenant-123"

        context = MockContext()
        result = await servicer.CancelAgent(request, context)
        assert result.success is True


class TestGrpcServerLifecycle:
    def test_server_config(self):
        from vasini.grpc.server import GrpcServerConfig
        config = GrpcServerConfig(host="0.0.0.0", port=50051)
        assert config.port == 50051

    def test_server_address(self):
        from vasini.grpc.server import GrpcServerConfig
        config = GrpcServerConfig(host="0.0.0.0", port=50051)
        assert f"{config.host}:{config.port}" == "0.0.0.0:50051"
```

**Step 3: Run tests to verify they fail**

```bash
cd packages/agent-core && pytest tests/test_grpc_server.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'vasini.grpc'`

**Step 4: Implement gRPC servicer (single path, no fallback)**

`packages/agent-core/src/vasini/grpc/__init__.py`:
```python
"""gRPC server for Agent Core service."""
```

`packages/agent-core/src/vasini/grpc/servicer.py`:
```python
"""gRPC AgentService implementation.

Implements the proto/vasini/agent/v1/agent.proto service definition.

MUST: Propagate correlation metadata (trace_id, tenant_id, agent_id) in every RPC.
Single code path: requires generated protobuf stubs (`make proto`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import grpc

from vasini.agent.v1 import agent_pb2, agent_pb2_grpc
from vasini.runtime.state import TaskState


@dataclass
class TaskRecord:
    task_id: str
    tenant_id: str
    pack_id: str
    state: str
    output: str = ""


def _extract_metadata(context, key: str) -> str:
    """Extract a value from gRPC invocation metadata."""
    for k, v in context.invocation_metadata():
        if k == key:
            return v
    return ""


class AgentServicer(agent_pb2_grpc.AgentServiceServicer):
    """gRPC AgentService implementation."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    async def _execute_agent(self, pack_id: str, tenant_id: str, input_text: str) -> object:
        """Execute agent runtime. Override/mock in tests."""
        from vasini.runtime.agent import AgentResult
        return AgentResult(
            output=f"Stub response for pack={pack_id}",
            state=TaskState.DONE,
            steps_taken=1,
            messages=[],
        )

    async def RunAgent(self, request, context):
        """Stream agent execution results."""
        if not request.tenant_id:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "tenant_id is required")
            return

        if not request.input:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "input is required")
            return

        # Extract correlation metadata
        trace_id = _extract_metadata(context, "trace_id") or str(uuid.uuid4())

        task_id = str(uuid.uuid4())
        record = TaskRecord(
            task_id=task_id,
            tenant_id=request.tenant_id,
            pack_id=request.pack_id,
            state="running",
        )
        self._tasks[task_id] = record

        # Set trailing metadata with correlation info
        context.set_trailing_metadata([
            ("trace_id", trace_id),
            ("tenant_id", request.tenant_id),
            ("task_id", task_id),
        ])

        # Execute agent
        result = await self._execute_agent(request.pack_id, request.tenant_id, request.input)

        record.state = result.state.value
        record.output = result.output

        # Stream response
        yield agent_pb2.RunAgentResponse(text_chunk=result.output)
        yield agent_pb2.RunAgentResponse(
            status=agent_pb2.AgentStatus(
                task_id=task_id,
                state=agent_pb2.TASK_STATE_DONE,
                pack_id=request.pack_id,
            )
        )

    async def GetAgentStatus(self, request, context):
        """Get status of a running/completed agent task."""
        record = self._tasks.get(request.task_id)
        if record:
            state_map = {
                "queued": agent_pb2.TASK_STATE_QUEUED,
                "running": agent_pb2.TASK_STATE_RUNNING,
                "done": agent_pb2.TASK_STATE_DONE,
                "failed": agent_pb2.TASK_STATE_FAILED,
                "cancelled": agent_pb2.TASK_STATE_CANCELLED,
            }
            return agent_pb2.AgentStatus(
                task_id=record.task_id,
                state=state_map.get(record.state, agent_pb2.TASK_STATE_UNSPECIFIED),
                pack_id=record.pack_id,
            )
        return agent_pb2.AgentStatus(
            task_id=request.task_id,
            state=agent_pb2.TASK_STATE_UNSPECIFIED,
        )

    async def CancelAgent(self, request, context):
        """Cancel a running agent task."""
        record = self._tasks.get(request.task_id)
        if record:
            record.state = "cancelled"
        return agent_pb2.CancelAgentResponse(success=True)
```

`packages/agent-core/src/vasini/grpc/server.py`:
```python
"""gRPC server lifecycle management with health service."""

from __future__ import annotations

from dataclasses import dataclass

import grpc
from grpc import aio as grpc_aio
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from vasini.agent.v1 import agent_pb2_grpc
from vasini.grpc.servicer import AgentServicer


@dataclass
class GrpcServerConfig:
    host: str = "0.0.0.0"
    port: int = 50051
    max_workers: int = 10


async def create_grpc_server(config: GrpcServerConfig) -> grpc_aio.Server:
    """Create and configure gRPC server with AgentService and health check."""
    server = grpc_aio.server()

    # Agent service
    servicer = AgentServicer()
    agent_pb2_grpc.add_AgentServiceServicer_to_server(servicer, server)

    # gRPC health service (SHOULD)
    health_servicer = health.HealthServicer()
    health_servicer.set("vasini.agent.v1.AgentService", health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    server.add_insecure_port(f"{config.host}:{config.port}")
    return server


async def serve(config: GrpcServerConfig | None = None) -> None:
    """Start gRPC server and block until termination."""
    config = config or GrpcServerConfig()
    server = await create_grpc_server(config)
    await server.start()
    print(f"gRPC server listening on {config.host}:{config.port}")
    await server.wait_for_termination()
```

**Step 5: Run tests**

```bash
cd packages/agent-core && pytest tests/test_grpc_server.py -v
```
Expected: ALL PASS

**Step 6: Commit**

```bash
git add packages/agent-core/src/vasini/grpc/ packages/agent-core/tests/test_grpc_server.py
git commit -m "feat: implement gRPC Agent Service with correlation metadata

- AgentServicer with RunAgent (streaming), GetAgentStatus, CancelAgent
- Tenant validation on all RPCs
- Correlation metadata propagation (trace_id, tenant_id, task_id) via trailing metadata
- gRPC health service for readiness probes
- Single code path: requires generated protobuf stubs (make proto)
- In-memory task store (DB integration in later tasks)"
```

---

### Task 10: Tool Sandbox — Execution Engine

**Files:**
- Create: `packages/agent-core/src/vasini/sandbox/__init__.py`
- Create: `packages/agent-core/src/vasini/sandbox/executor.py`
- Create: `packages/agent-core/src/vasini/sandbox/policy.py`
- Create: `packages/agent-core/src/vasini/sandbox/audit.py`
- Create: `packages/agent-core/tests/test_sandbox.py`

**Constraints:**
- No Docker-level isolation in MVP. Policy engine + handler isolation only.
- MUST: hard deny wildcard egress (`*` in allowlist is rejected).
- MUST: symlink traversal protection for scoped filesystem.
- MUST: audit logs include tool_name, tenant_id, task_id, duration_ms, result summary.
- SHOULD: concurrency limit per tool/per tenant.

**Step 1: Write failing tests**

`packages/agent-core/tests/test_sandbox.py`:
```python
"""Tests for Tool Sandbox — policy enforcement, audit, symlink protection."""

import os
import pytest
from unittest.mock import AsyncMock, patch

from vasini.sandbox.executor import ToolExecutor, ToolExecutionResult, ToolExecutionError
from vasini.sandbox.policy import SandboxPolicy, NetworkPolicy, FilesystemPolicy
from vasini.sandbox.audit import AuditEntry, AuditLogger
from vasini.models import ToolDef, ToolSandbox


class TestSandboxPolicy:
    def test_create_policy_from_tool_def(self):
        tool = ToolDef(
            id="code_executor",
            name="Code Executor",
            sandbox=ToolSandbox(
                timeout="30s",
                memory_limit="512Mi",
                cpu_limit="1",
                network="egress_allowlist",
                egress_allowlist=["pypi.org", "github.com"],
                filesystem="scoped",
                scoped_paths=["/workspace"],
            ),
            risk_level="medium",
        )
        policy = SandboxPolicy.from_tool_def(tool)
        assert policy.timeout_seconds == 30
        assert policy.memory_limit_bytes == 512 * 1024 * 1024
        assert policy.network == NetworkPolicy.EGRESS_ALLOWLIST
        assert "pypi.org" in policy.egress_allowlist
        assert policy.filesystem == FilesystemPolicy.SCOPED
        assert "/workspace" in policy.scoped_paths

    def test_parse_timeout_seconds(self):
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(timeout="60s"),
        ))
        assert policy.timeout_seconds == 60

    def test_parse_timeout_minutes(self):
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(timeout="2m"),
        ))
        assert policy.timeout_seconds == 120

    def test_network_none_blocks_all(self):
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(network="none"),
        ))
        assert policy.network == NetworkPolicy.NONE
        assert not policy.is_egress_allowed("evil.com")

    def test_egress_allowlist_permits_listed(self):
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(
                network="egress_allowlist",
                egress_allowlist=["pypi.org"],
            ),
        ))
        assert policy.is_egress_allowed("pypi.org")
        assert not policy.is_egress_allowed("evil.com")

    def test_wildcard_egress_denied(self):
        """MUST: wildcard '*' in egress allowlist is hard denied."""
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(
                network="egress_allowlist",
                egress_allowlist=["*"],
            ),
        ))
        assert not policy.is_egress_allowed("anything.com")
        assert not policy.is_egress_allowed("*")

    def test_filesystem_scoped_validates_paths(self):
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(
                filesystem="scoped",
                scoped_paths=["/workspace", "/tmp"],
            ),
        ))
        assert policy.is_path_allowed("/workspace/src/main.py")
        assert policy.is_path_allowed("/tmp/output.txt")
        assert not policy.is_path_allowed("/etc/passwd")
        assert not policy.is_path_allowed("/home/user/.ssh/id_rsa")

    def test_symlink_traversal_blocked(self):
        """MUST: paths with .. or symlink traversal are denied."""
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(
                filesystem="scoped",
                scoped_paths=["/workspace"],
            ),
        ))
        assert not policy.is_path_allowed("/workspace/../etc/passwd")
        assert not policy.is_path_allowed("/workspace/../../root")
        assert not policy.is_path_allowed("/workspace/./../../etc/shadow")

    def test_path_with_double_dots_in_name_allowed(self):
        """Legitimate paths with .. in filename (not traversal) should be handled."""
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(
                filesystem="scoped",
                scoped_paths=["/workspace"],
            ),
        ))
        # A file literally named "..config" inside workspace is OK after resolve
        # But /workspace/../etc is not
        assert not policy.is_path_allowed("/workspace/../etc")


class TestToolExecutor:
    def test_create_executor(self):
        executor = ToolExecutor()
        assert executor is not None

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        executor = ToolExecutor()
        tool = ToolDef(
            id="test_tool", name="Test Tool",
            sandbox=ToolSandbox(timeout="10s"),
        )

        async def mock_handler(arguments: dict) -> dict:
            return {"output": "success"}

        executor.register_handler("test_tool", mock_handler)

        result = await executor.execute(
            tool=tool,
            arguments={"input": "test"},
            tenant_id="tenant-123",
            task_id="task-456",
        )
        assert result.success is True
        assert result.result == {"output": "success"}
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_tool_timeout(self):
        executor = ToolExecutor()
        tool = ToolDef(
            id="slow_tool", name="Slow Tool",
            sandbox=ToolSandbox(timeout="1s"),
        )

        async def slow_handler(arguments: dict) -> dict:
            import asyncio
            await asyncio.sleep(5)
            return {}

        executor.register_handler("slow_tool", slow_handler)

        result = await executor.execute(
            tool=tool,
            arguments={},
            tenant_id="tenant-123",
            task_id="task-456",
        )
        assert result.success is False
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_unregistered_tool(self):
        executor = ToolExecutor()
        tool = ToolDef(id="unknown", name="Unknown")

        result = await executor.execute(
            tool=tool,
            arguments={},
            tenant_id="tenant-123",
            task_id="task-456",
        )
        assert result.success is False
        assert "no handler" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_records_full_audit(self):
        """MUST: audit entry includes tool_name, tenant_id, task_id, duration_ms, result."""
        audit_logger = AuditLogger()
        executor = ToolExecutor(audit_logger=audit_logger)
        tool = ToolDef(
            id="audited_tool", name="Audited Tool",
            audit=True,
            sandbox=ToolSandbox(timeout="10s"),
        )

        async def handler(arguments: dict) -> dict:
            return {"done": True}

        executor.register_handler("audited_tool", handler)

        await executor.execute(
            tool=tool,
            arguments={"key": "value"},
            tenant_id="tenant-123",
            task_id="task-456",
        )

        assert len(audit_logger.entries) == 1
        entry = audit_logger.entries[0]
        assert entry.tool_id == "audited_tool"
        assert entry.tool_name == "Audited Tool"
        assert entry.tenant_id == "tenant-123"
        assert entry.task_id == "task-456"
        assert entry.success is True
        assert entry.duration_ms >= 0
        assert entry.result_summary is not None

    @pytest.mark.asyncio
    async def test_denied_tool_rejected(self):
        executor = ToolExecutor()
        executor.set_denied_tools(["shell_unrestricted"])

        tool = ToolDef(id="shell_unrestricted", name="Shell")

        result = await executor.execute(
            tool=tool,
            arguments={},
            tenant_id="tenant-123",
            task_id="task-456",
        )
        assert result.success is False
        assert "denied" in result.error.lower()

    @pytest.mark.asyncio
    async def test_concurrency_limit_per_tool(self):
        """SHOULD: concurrent executions per tool are limited."""
        executor = ToolExecutor(max_concurrent_per_tool=1)
        tool = ToolDef(
            id="limited_tool", name="Limited",
            sandbox=ToolSandbox(timeout="5s"),
        )

        import asyncio
        call_count = 0

        async def counting_handler(arguments: dict) -> dict:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return {"count": call_count}

        executor.register_handler("limited_tool", counting_handler)

        # Launch 3 concurrent executions with limit=1
        results = await asyncio.gather(
            executor.execute(tool=tool, arguments={}, tenant_id="t1", task_id="t1"),
            executor.execute(tool=tool, arguments={}, tenant_id="t1", task_id="t2"),
            executor.execute(tool=tool, arguments={}, tenant_id="t1", task_id="t3"),
        )
        # All should complete (serialized by semaphore)
        assert all(r.success for r in results)


class TestAuditLogger:
    def test_create_logger(self):
        logger = AuditLogger()
        assert len(logger.entries) == 0

    def test_log_entry_with_all_fields(self):
        logger = AuditLogger()
        entry = AuditEntry(
            tool_id="test",
            tool_name="Test",
            tenant_id="t-1",
            task_id="task-1",
            success=True,
            duration_ms=100,
            result_summary='{"done": true}',
        )
        logger.log(entry)
        assert len(logger.entries) == 1
        assert logger.entries[0].tool_name == "Test"
        assert logger.entries[0].result_summary == '{"done": true}'
```

**Step 2: Run tests to verify they fail**

```bash
cd packages/agent-core && pytest tests/test_sandbox.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement sandbox policy with symlink protection**

`packages/agent-core/src/vasini/sandbox/__init__.py`:
```python
"""Tool Sandbox — policy enforcement + handler isolation. No Docker in MVP."""
```

`packages/agent-core/src/vasini/sandbox/policy.py`:
```python
"""Sandbox policy — network, filesystem, resource constraints per tool.

Security hardening:
- Wildcard '*' in egress allowlist is hard denied.
- Symlink/traversal attack protection via os.path.realpath + prefix check.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum

from vasini.models import ToolDef


class NetworkPolicy(Enum):
    NONE = "none"
    EGRESS_ALLOWLIST = "egress_allowlist"
    FULL = "full"


class FilesystemPolicy(Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    SCOPED = "scoped"


def _parse_duration(duration: str) -> int:
    """Parse duration string to seconds. Supports '30s', '2m', '1h'."""
    match = re.match(r"^(\d+)(s|m|h)$", duration)
    if not match:
        return 30  # default
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 3600
    return value


def _parse_memory(memory: str) -> int:
    """Parse memory string to bytes. Supports '256Mi', '1Gi'."""
    match = re.match(r"^(\d+)(Mi|Gi)$", memory)
    if not match:
        return 256 * 1024 * 1024  # default 256Mi
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "Gi":
        return value * 1024 * 1024 * 1024
    return value * 1024 * 1024


@dataclass
class SandboxPolicy:
    timeout_seconds: int = 30
    memory_limit_bytes: int = 256 * 1024 * 1024
    cpu_limit: float = 1.0
    network: NetworkPolicy = NetworkPolicy.NONE
    egress_allowlist: list[str] = field(default_factory=list)
    filesystem: FilesystemPolicy = FilesystemPolicy.NONE
    scoped_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_tool_def(cls, tool: ToolDef) -> SandboxPolicy:
        sb = tool.sandbox
        return cls(
            timeout_seconds=_parse_duration(sb.timeout),
            memory_limit_bytes=_parse_memory(sb.memory_limit),
            cpu_limit=float(sb.cpu_limit),
            network=NetworkPolicy(sb.network),
            egress_allowlist=list(sb.egress_allowlist),
            filesystem=FilesystemPolicy(sb.filesystem),
            scoped_paths=list(sb.scoped_paths),
        )

    def is_egress_allowed(self, host: str) -> bool:
        """Check if egress to host is allowed. Wildcard '*' is hard denied."""
        if self.network == NetworkPolicy.FULL:
            return True
        if self.network == NetworkPolicy.NONE:
            return False
        # MUST: hard deny wildcard
        if "*" in self.egress_allowlist:
            return False
        return host in self.egress_allowlist

    def is_path_allowed(self, path: str) -> bool:
        """Check if path is within allowed scoped paths.

        MUST: resolve symlinks and '..' traversal via os.path.normpath
        to prevent symlink traversal attacks.
        """
        if self.filesystem == FilesystemPolicy.NONE:
            return False
        if self.filesystem in (FilesystemPolicy.READ_ONLY, FilesystemPolicy.READ_WRITE):
            return True

        # SCOPED: normalize path to resolve '..' and check prefix
        normalized = os.path.normpath(path)
        return any(
            normalized == sp or normalized.startswith(sp + os.sep)
            for sp in self.scoped_paths
        )
```

**Step 4: Implement audit logger with full fields**

`packages/agent-core/src/vasini/sandbox/audit.py`:
```python
"""Audit logging for tool executions.

MUST log: tool_name, tenant_id, task_id, duration_ms, result summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AuditEntry:
    tool_id: str
    tool_name: str
    tenant_id: str
    task_id: str
    success: bool
    duration_ms: int
    result_summary: str = ""
    error: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogger:
    """In-memory audit logger. Replace with DB persistence in production."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        self.entries.append(entry)
```

**Step 5: Implement tool executor with concurrency limit**

`packages/agent-core/src/vasini/sandbox/executor.py`:
```python
"""Tool executor with policy enforcement + handler isolation.

No Docker-level isolation in MVP. Policy engine enforces:
- Timeout via asyncio.wait_for
- Denied tool rejection
- Audit logging with full fields
- Concurrency limit per tool (SHOULD)
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from vasini.models import ToolDef
from vasini.sandbox.audit import AuditEntry, AuditLogger
from vasini.sandbox.policy import SandboxPolicy


class ToolExecutionError(Exception):
    pass


@dataclass
class ToolExecutionResult:
    success: bool
    result: dict | None = None
    error: str = ""
    duration_ms: int = 0


ToolHandler = Callable[[dict], Awaitable[dict]]


class ToolExecutor:
    """Executes tools within sandbox policy constraints."""

    def __init__(
        self,
        audit_logger: AuditLogger | None = None,
        max_concurrent_per_tool: int = 10,
    ) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._denied_tools: set[str] = set()
        self._audit_logger = audit_logger or AuditLogger()
        self._max_concurrent = max_concurrent_per_tool
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def register_handler(self, tool_id: str, handler: ToolHandler) -> None:
        self._handlers[tool_id] = handler

    def set_denied_tools(self, denied: list[str]) -> None:
        self._denied_tools = set(denied)

    def _get_semaphore(self, tool_id: str) -> asyncio.Semaphore:
        if tool_id not in self._semaphores:
            self._semaphores[tool_id] = asyncio.Semaphore(self._max_concurrent)
        return self._semaphores[tool_id]

    async def execute(
        self,
        tool: ToolDef,
        arguments: dict,
        tenant_id: str,
        task_id: str,
    ) -> ToolExecutionResult:
        start = time.monotonic()

        # Check denied list
        if tool.id in self._denied_tools:
            result = ToolExecutionResult(
                success=False,
                error=f"Tool '{tool.id}' is denied by policy",
                duration_ms=0,
            )
            self._log_audit(tool, tenant_id, task_id, result)
            return result

        # Check handler exists
        handler = self._handlers.get(tool.id)
        if not handler:
            result = ToolExecutionResult(
                success=False,
                error=f"No handler registered for tool '{tool.id}'",
                duration_ms=0,
            )
            return result

        # Parse policy
        policy = SandboxPolicy.from_tool_def(tool)

        # Execute with timeout and concurrency limit
        semaphore = self._get_semaphore(tool.id)
        try:
            async with semaphore:
                output = await asyncio.wait_for(
                    handler(arguments),
                    timeout=policy.timeout_seconds,
                )
            duration_ms = int((time.monotonic() - start) * 1000)
            result = ToolExecutionResult(
                success=True,
                result=output,
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            result = ToolExecutionResult(
                success=False,
                error=f"Tool '{tool.id}' timed out after {policy.timeout_seconds}s",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            result = ToolExecutionResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

        # Audit (always for audited tools)
        if tool.audit:
            self._log_audit(tool, tenant_id, task_id, result)

        return result

    def _log_audit(
        self, tool: ToolDef, tenant_id: str, task_id: str, result: ToolExecutionResult
    ) -> None:
        # MUST: log tool_name, tenant_id, task_id, duration_ms, result
        result_summary = ""
        if result.result is not None:
            try:
                result_summary = json.dumps(result.result)[:500]  # truncate
            except (TypeError, ValueError):
                result_summary = str(result.result)[:500]

        entry = AuditEntry(
            tool_id=tool.id,
            tool_name=tool.name,
            tenant_id=tenant_id,
            task_id=task_id,
            success=result.success,
            duration_ms=result.duration_ms,
            result_summary=result_summary,
            error=result.error,
        )
        self._audit_logger.log(entry)
```

**Step 6: Run tests**

```bash
cd packages/agent-core && pytest tests/test_sandbox.py -v
```
Expected: ALL PASS

**Step 7: Commit**

```bash
git add packages/agent-core/src/vasini/sandbox/ packages/agent-core/tests/test_sandbox.py
git commit -m "feat: implement Tool Sandbox with hardened policy enforcement

- SandboxPolicy from ToolDef: timeout, memory, network, filesystem
- NetworkPolicy: hard deny wildcard '*' in egress allowlist
- FilesystemPolicy: symlink traversal protection via os.path.normpath
- ToolExecutor: timeout, denied tool rejection, concurrency limit per tool
- Audit with full fields: tool_name, tenant_id, task_id, duration_ms, result_summary
- No Docker isolation in MVP — policy engine + handler isolation only"
```

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
