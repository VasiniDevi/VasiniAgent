"""Audit logging for tool executions."""

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
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        self.entries.append(entry)
