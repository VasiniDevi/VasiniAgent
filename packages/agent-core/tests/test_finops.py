"""Tests for FinOps — token accounting, budget caps."""

import pytest
from vasini.finops.accounting import TokenAccounting, UsageRecord, ModelTier
from vasini.finops.budget import (
    BudgetManager, TenantBudget, BudgetStatus,
    BudgetCheckResult, BudgetAction,
)


class TestTokenAccounting:
    def test_record_usage(self):
        accounting = TokenAccounting()
        accounting.record(
            tenant_id="t1",
            model="claude-opus-4",
            input_tokens=1000,
            output_tokens=500,
        )
        usage = accounting.get_usage("t1")
        assert usage.total_input_tokens == 1000
        assert usage.total_output_tokens == 500

    def test_accumulate_usage(self):
        accounting = TokenAccounting()
        accounting.record("t1", "claude-opus-4", 1000, 500)
        accounting.record("t1", "claude-opus-4", 2000, 1000)
        usage = accounting.get_usage("t1")
        assert usage.total_input_tokens == 3000
        assert usage.total_output_tokens == 1500

    def test_per_model_breakdown(self):
        accounting = TokenAccounting()
        accounting.record("t1", "claude-opus-4", 1000, 500)
        accounting.record("t1", "claude-haiku-4", 5000, 2000)
        breakdown = accounting.get_model_breakdown("t1")
        assert "claude-opus-4" in breakdown
        assert "claude-haiku-4" in breakdown
        assert breakdown["claude-opus-4"].total_input_tokens == 1000
        assert breakdown["claude-haiku-4"].total_input_tokens == 5000

    def test_multi_tenant_isolation(self):
        accounting = TokenAccounting()
        accounting.record("t1", "model-a", 1000, 500)
        accounting.record("t2", "model-a", 2000, 1000)
        assert accounting.get_usage("t1").total_input_tokens == 1000
        assert accounting.get_usage("t2").total_input_tokens == 2000

    def test_empty_usage(self):
        accounting = TokenAccounting()
        usage = accounting.get_usage("unknown")
        assert usage.total_input_tokens == 0
        assert usage.total_output_tokens == 0

    def test_cost_estimation(self):
        accounting = TokenAccounting()
        accounting.set_pricing("claude-opus-4", input_per_1k=0.015, output_per_1k=0.075)
        accounting.record("t1", "claude-opus-4", 10000, 5000)
        cost = accounting.estimate_cost("t1")
        assert cost > 0
        assert abs(cost - 0.525) < 0.01


class TestBudgetManager:
    def test_create_budget(self):
        mgr = BudgetManager()
        budget = mgr.set_budget("t1", soft_cap=100.0, hard_cap=150.0)
        assert budget.soft_cap == 100.0
        assert budget.hard_cap == 150.0

    def test_check_under_budget(self):
        mgr = BudgetManager()
        mgr.set_budget("t1", soft_cap=100.0, hard_cap=150.0)
        result = mgr.check("t1", current_spend=50.0)
        assert result.action == BudgetAction.ALLOW
        assert result.status == BudgetStatus.OK

    def test_check_soft_cap_warning(self):
        mgr = BudgetManager()
        mgr.set_budget("t1", soft_cap=100.0, hard_cap=150.0)
        result = mgr.check("t1", current_spend=110.0)
        assert result.action == BudgetAction.WARN
        assert result.status == BudgetStatus.SOFT_CAP_EXCEEDED

    def test_check_hard_cap_blocks(self):
        mgr = BudgetManager()
        mgr.set_budget("t1", soft_cap=100.0, hard_cap=150.0)
        result = mgr.check("t1", current_spend=160.0)
        assert result.action == BudgetAction.BLOCK
        assert result.status == BudgetStatus.HARD_CAP_EXCEEDED

    def test_no_budget_allows(self):
        mgr = BudgetManager()
        result = mgr.check("unknown", current_spend=99999.0)
        assert result.action == BudgetAction.ALLOW

    def test_at_exact_soft_cap(self):
        mgr = BudgetManager()
        mgr.set_budget("t1", soft_cap=100.0, hard_cap=150.0)
        result = mgr.check("t1", current_spend=100.0)
        assert result.action == BudgetAction.WARN

    def test_at_exact_hard_cap(self):
        mgr = BudgetManager()
        mgr.set_budget("t1", soft_cap=100.0, hard_cap=150.0)
        result = mgr.check("t1", current_spend=150.0)
        assert result.action == BudgetAction.BLOCK
