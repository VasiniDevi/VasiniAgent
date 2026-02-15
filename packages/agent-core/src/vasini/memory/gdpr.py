"""GDPR compliance — cascade delete + data export."""

from __future__ import annotations

from dataclasses import dataclass

from vasini.memory.short_term import ShortTermStore
from vasini.memory.factual import FactualStore


@dataclass
class DeleteResult:
    success: bool
    tenant_id: str
    stores_cleared: list[str]


class GDPRManager:
    def __init__(self, short_term: ShortTermStore, factual: FactualStore) -> None:
        self._short_term = short_term
        self._factual = factual

    def delete_tenant_data(self, tenant_id: str) -> DeleteResult:
        self._short_term.delete_tenant(tenant_id)
        self._factual.delete_tenant(tenant_id)
        return DeleteResult(
            success=True,
            tenant_id=tenant_id,
            stores_cleared=["short_term", "factual"],
        )

    def export_tenant_data(self, tenant_id: str) -> dict:
        factual_data = []
        prefix = f"{tenant_id}:"
        for ck, records in self._factual._records.items():
            if ck.startswith(prefix):
                for r in records:
                    factual_data.append({
                        "key": r.key, "value": r.value,
                        "version": r.version, "evidence": r.evidence,
                        "confidence": r.confidence,
                    })
        return {
            "short_term": [],
            "factual": factual_data,
        }
