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
