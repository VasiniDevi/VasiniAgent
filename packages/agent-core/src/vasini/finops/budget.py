"""Budget cap enforcement — soft (alert) + hard (block)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BudgetStatus(Enum):
    OK = "ok"
    SOFT_CAP_EXCEEDED = "soft_cap_exceeded"
    HARD_CAP_EXCEEDED = "hard_cap_exceeded"


class BudgetAction(Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class TenantBudget:
    tenant_id: str
    soft_cap: float
    hard_cap: float


@dataclass
class BudgetCheckResult:
    action: BudgetAction
    status: BudgetStatus
    current_spend: float = 0.0
    remaining: float = 0.0


class BudgetManager:
    def __init__(self) -> None:
        self._budgets: dict[str, TenantBudget] = {}

    def set_budget(self, tenant_id: str, soft_cap: float, hard_cap: float) -> TenantBudget:
        budget = TenantBudget(tenant_id=tenant_id, soft_cap=soft_cap, hard_cap=hard_cap)
        self._budgets[tenant_id] = budget
        return budget

    def check(self, tenant_id: str, current_spend: float) -> BudgetCheckResult:
        budget = self._budgets.get(tenant_id)
        if not budget:
            return BudgetCheckResult(
                action=BudgetAction.ALLOW,
                status=BudgetStatus.OK,
                current_spend=current_spend,
            )

        if current_spend >= budget.hard_cap:
            return BudgetCheckResult(
                action=BudgetAction.BLOCK,
                status=BudgetStatus.HARD_CAP_EXCEEDED,
                current_spend=current_spend,
                remaining=0.0,
            )

        if current_spend >= budget.soft_cap:
            return BudgetCheckResult(
                action=BudgetAction.WARN,
                status=BudgetStatus.SOFT_CAP_EXCEEDED,
                current_spend=current_spend,
                remaining=budget.hard_cap - current_spend,
            )

        return BudgetCheckResult(
            action=BudgetAction.ALLOW,
            status=BudgetStatus.OK,
            current_spend=current_spend,
            remaining=budget.hard_cap - current_spend,
        )
