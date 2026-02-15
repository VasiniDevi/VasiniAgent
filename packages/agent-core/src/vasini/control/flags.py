"""Feature flags — per-tenant toggles with percentage rollout."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FeatureFlag:
    id: str
    name: str
    enabled: bool
    rollout_percentage: int = 100  # 0-100
    tenant_overrides: dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FeatureFlagStore:
    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}

    def create(self, name: str, enabled: bool = False, rollout_percentage: int = 100) -> FeatureFlag:
        flag = FeatureFlag(
            id=name,
            name=name,
            enabled=enabled,
            rollout_percentage=rollout_percentage,
        )
        self._flags[name] = flag
        return flag

    def get(self, name: str) -> FeatureFlag | None:
        return self._flags.get(name)

    def set_tenant_override(self, flag_name: str, tenant_id: str, enabled: bool) -> None:
        flag = self._flags.get(flag_name)
        if flag:
            flag.tenant_overrides[tenant_id] = enabled

    def is_enabled(self, flag_name: str, tenant_id: str | None = None) -> bool:
        flag = self._flags.get(flag_name)
        if not flag:
            return False
        if not flag.enabled:
            if tenant_id and tenant_id in flag.tenant_overrides:
                return flag.tenant_overrides[tenant_id]
            return False
        if tenant_id and tenant_id in flag.tenant_overrides:
            return flag.tenant_overrides[tenant_id]
        if flag.rollout_percentage < 100 and tenant_id:
            hash_val = int(hashlib.md5(f"{flag_name}:{tenant_id}".encode()).hexdigest(), 16)
            return (hash_val % 100) < flag.rollout_percentage
        return flag.enabled

    def list_all(self) -> list[FeatureFlag]:
        return list(self._flags.values())
