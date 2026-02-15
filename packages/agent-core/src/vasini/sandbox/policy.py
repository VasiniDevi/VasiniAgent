"""Sandbox policy — network, filesystem, resource constraints per tool."""

from __future__ import annotations

import os
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


@dataclass
class SandboxPolicy:
    timeout_seconds: int = 30
    network: NetworkPolicy = NetworkPolicy.NONE
    egress_allowlist: list[str] = field(default_factory=list)
    filesystem: FilesystemPolicy = FilesystemPolicy.NONE
    scoped_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_tool_def(cls, tool: ToolDef) -> SandboxPolicy:
        sb = tool.sandbox
        return cls(
            timeout_seconds=sb.timeout,
            network=NetworkPolicy(sb.network),
            egress_allowlist=list(sb.egress_allowlist),
            filesystem=FilesystemPolicy(sb.filesystem),
            scoped_paths=list(sb.scoped_paths),
        )

    def is_egress_allowed(self, host: str) -> bool:
        if self.network == NetworkPolicy.FULL:
            return True
        if self.network == NetworkPolicy.NONE:
            return False
        if "*" in self.egress_allowlist:
            return False
        return host in self.egress_allowlist

    def is_path_allowed(self, path: str) -> bool:
        if self.filesystem == FilesystemPolicy.NONE:
            return False
        if self.filesystem in (FilesystemPolicy.READ_ONLY, FilesystemPolicy.READ_WRITE):
            return True
        normalized = os.path.normpath(path)
        return any(
            normalized == sp or normalized.startswith(sp + os.sep)
            for sp in self.scoped_paths
        )
