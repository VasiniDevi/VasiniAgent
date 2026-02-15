"""Token accounting per tenant/model with cost estimation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModelTier(Enum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


@dataclass
class UsageRecord:
    total_input_tokens: int = 0
    total_output_tokens: int = 0


@dataclass
class ModelPricing:
    input_per_1k: float = 0.0
    output_per_1k: float = 0.0


class TokenAccounting:
    def __init__(self) -> None:
        self._usage: dict[str, dict[str, UsageRecord]] = {}
        self._pricing: dict[str, ModelPricing] = {}

    def record(self, tenant_id: str, model: str, input_tokens: int, output_tokens: int) -> None:
        if tenant_id not in self._usage:
            self._usage[tenant_id] = {}
        if model not in self._usage[tenant_id]:
            self._usage[tenant_id][model] = UsageRecord()
        rec = self._usage[tenant_id][model]
        rec.total_input_tokens += input_tokens
        rec.total_output_tokens += output_tokens

    def get_usage(self, tenant_id: str) -> UsageRecord:
        models = self._usage.get(tenant_id, {})
        total = UsageRecord()
        for rec in models.values():
            total.total_input_tokens += rec.total_input_tokens
            total.total_output_tokens += rec.total_output_tokens
        return total

    def get_model_breakdown(self, tenant_id: str) -> dict[str, UsageRecord]:
        return dict(self._usage.get(tenant_id, {}))

    def set_pricing(self, model: str, input_per_1k: float, output_per_1k: float) -> None:
        self._pricing[model] = ModelPricing(input_per_1k=input_per_1k, output_per_1k=output_per_1k)

    def estimate_cost(self, tenant_id: str) -> float:
        total = 0.0
        for model, rec in self._usage.get(tenant_id, {}).items():
            pricing = self._pricing.get(model)
            if pricing:
                total += (rec.total_input_tokens / 1000) * pricing.input_per_1k
                total += (rec.total_output_tokens / 1000) * pricing.output_per_1k
        return total
