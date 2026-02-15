"""Tool executor with policy enforcement + handler isolation."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
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

        if tool.id in self._denied_tools:
            result = ToolExecutionResult(
                success=False,
                error=f"Tool '{tool.id}' is denied by policy",
                duration_ms=0,
            )
            self._log_audit(tool, tenant_id, task_id, result)
            return result

        handler = self._handlers.get(tool.id)
        if not handler:
            return ToolExecutionResult(
                success=False,
                error=f"No handler registered for tool '{tool.id}'",
                duration_ms=0,
            )

        policy = SandboxPolicy.from_tool_def(tool)
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
                error=f"Tool '{tool.id}' timeout after {policy.timeout_seconds}s",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            result = ToolExecutionResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

        if tool.audit:
            self._log_audit(tool, tenant_id, task_id, result)

        return result

    def _log_audit(
        self, tool: ToolDef, tenant_id: str, task_id: str, result: ToolExecutionResult
    ) -> None:
        result_summary = ""
        if result.result is not None:
            try:
                result_summary = json.dumps(result.result)[:500]
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
