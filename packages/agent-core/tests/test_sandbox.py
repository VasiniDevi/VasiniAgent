"""Tests for Tool Sandbox — policy enforcement, audit, symlink protection."""

import os
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from vasini.sandbox.executor import ToolExecutor, ToolExecutionResult
from vasini.sandbox.policy import SandboxPolicy, NetworkPolicy, FilesystemPolicy
from vasini.sandbox.audit import AuditEntry, AuditLogger
from vasini.models import ToolDef, ToolSandbox


class TestSandboxPolicy:
    def test_create_policy_from_tool_def(self):
        tool = ToolDef(
            id="code_executor",
            name="Code Executor",
            sandbox=ToolSandbox(
                timeout=30,
                memory="512Mi",
                cpu=1.0,
                network="egress_allowlist",
                egress_allowlist=["pypi.org", "github.com"],
                filesystem="scoped",
                scoped_paths=["/workspace"],
            ),
            risk_level="medium",
        )
        policy = SandboxPolicy.from_tool_def(tool)
        assert policy.timeout_seconds == 30
        assert policy.network == NetworkPolicy.EGRESS_ALLOWLIST
        assert "pypi.org" in policy.egress_allowlist
        assert policy.filesystem == FilesystemPolicy.SCOPED
        assert "/workspace" in policy.scoped_paths

    def test_default_timeout(self):
        policy = SandboxPolicy.from_tool_def(ToolDef(id="test", name="Test"))
        assert policy.timeout_seconds == 30

    def test_custom_timeout(self):
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(timeout=120),
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
        """MUST: paths with .. traversal are denied."""
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

    def test_path_traversal_does_not_escape(self):
        policy = SandboxPolicy.from_tool_def(ToolDef(
            id="test", name="Test",
            sandbox=ToolSandbox(
                filesystem="scoped",
                scoped_paths=["/workspace"],
            ),
        ))
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
            sandbox=ToolSandbox(timeout=10),
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
            sandbox=ToolSandbox(timeout=1),
        )

        async def slow_handler(arguments: dict) -> dict:
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
            sandbox=ToolSandbox(timeout=10),
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
            sandbox=ToolSandbox(timeout=5),
        )

        call_count = 0

        async def counting_handler(arguments: dict) -> dict:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return {"count": call_count}

        executor.register_handler("limited_tool", counting_handler)

        results = await asyncio.gather(
            executor.execute(tool=tool, arguments={}, tenant_id="t1", task_id="t1"),
            executor.execute(tool=tool, arguments={}, tenant_id="t1", task_id="t2"),
            executor.execute(tool=tool, arguments={}, tenant_id="t1", task_id="t3"),
        )
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
