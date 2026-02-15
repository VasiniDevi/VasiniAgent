"""Short-term memory store — in-memory with TTL + LRU eviction.

Production: Redis adapter with TTL via EXPIRE.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class _Entry:
    value: str
    expires_at: float


class ShortTermStore:
    def __init__(self, max_entries: int = 100, default_ttl_seconds: float = 86400) -> None:
        self._max = max_entries
        self._ttl = default_ttl_seconds
        self._data: OrderedDict[str, _Entry] = OrderedDict()

    def _key(self, tenant_id: str, agent_id: str, key: str) -> str:
        return f"{tenant_id}:{agent_id}:{key}"

    def set(self, tenant_id: str, agent_id: str, key: str, value: str, ttl: float | None = None) -> None:
        full_key = self._key(tenant_id, agent_id, key)
        expires = time.monotonic() + (ttl if ttl is not None else self._ttl)
        if full_key in self._data:
            self._data.move_to_end(full_key)
        self._data[full_key] = _Entry(value=value, expires_at=expires)
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def get(self, tenant_id: str, agent_id: str, key: str) -> str | None:
        full_key = self._key(tenant_id, agent_id, key)
        entry = self._data.get(full_key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._data[full_key]
            return None
        self._data.move_to_end(full_key)
        return entry.value

    def delete(self, tenant_id: str, agent_id: str, key: str) -> None:
        full_key = self._key(tenant_id, agent_id, key)
        self._data.pop(full_key, None)

    def delete_tenant(self, tenant_id: str) -> None:
        prefix = f"{tenant_id}:"
        keys_to_delete = [k for k in self._data if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._data[k]
