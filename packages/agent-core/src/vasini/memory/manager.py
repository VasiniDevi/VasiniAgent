"""Memory Manager — unified interface for all memory stores."""

from __future__ import annotations

from vasini.memory.short_term import ShortTermStore
from vasini.memory.factual import FactualStore
from vasini.memory.gdpr import GDPRManager, DeleteResult


class MemoryManager:
    def __init__(
        self,
        max_short_term_entries: int = 100,
        min_factual_confidence: float = 0.0,
    ) -> None:
        self.short_term = ShortTermStore(max_entries=max_short_term_entries)
        self.factual = FactualStore(min_confidence=min_factual_confidence)
        self._gdpr = GDPRManager(short_term=self.short_term, factual=self.factual)

    def gdpr_delete(self, tenant_id: str) -> DeleteResult:
        return self._gdpr.delete_tenant_data(tenant_id)

    def gdpr_export(self, tenant_id: str) -> dict:
        return self._gdpr.export_tenant_data(tenant_id)
