"""Factual memory — append-only versioned records.

Production: PostgreSQL with the memory_factual table from Task 6.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FactualRecord:
    id: str
    tenant_id: str
    agent_id: str
    key: str
    value: str
    version: int
    evidence: str
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FactualStore:
    def __init__(self, min_confidence: float = 0.0) -> None:
        self._min_confidence = min_confidence
        self._records: dict[str, list[FactualRecord]] = {}

    def _composite_key(self, tenant_id: str, agent_id: str, key: str) -> str:
        return f"{tenant_id}:{agent_id}:{key}"

    def write(
        self,
        tenant_id: str, agent_id: str, key: str,
        value: str, evidence: str, confidence: float,
    ) -> FactualRecord:
        if confidence < self._min_confidence:
            raise ValueError(f"Confidence {confidence} below minimum {self._min_confidence}")

        ck = self._composite_key(tenant_id, agent_id, key)
        versions = self._records.get(ck, [])
        version = len(versions) + 1

        record = FactualRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
            key=key,
            value=value,
            version=version,
            evidence=evidence,
            confidence=confidence,
        )
        if ck not in self._records:
            self._records[ck] = []
        self._records[ck].append(record)
        return record

    def get_latest(self, tenant_id: str, agent_id: str, key: str) -> FactualRecord | None:
        ck = self._composite_key(tenant_id, agent_id, key)
        versions = self._records.get(ck, [])
        return versions[-1] if versions else None

    def get_versions(self, tenant_id: str, agent_id: str, key: str) -> list[FactualRecord]:
        ck = self._composite_key(tenant_id, agent_id, key)
        return list(self._records.get(ck, []))

    def delete_tenant(self, tenant_id: str) -> None:
        prefix = f"{tenant_id}:"
        keys_to_delete = [k for k in self._records if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._records[k]
