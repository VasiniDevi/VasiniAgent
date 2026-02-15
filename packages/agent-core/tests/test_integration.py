"""Integration smoke tests — wires together components from all phases.

Each test validates a cross-component scenario using actual APIs (no mocks).
"""

from __future__ import annotations

import asyncio

import pytest

# ── Policy + Firewall ─────────────────────────────────────────────────────
from vasini.policy.engine import PolicyEngine
from vasini.policy.rules import PolicyVerdict
from vasini.models import (
    Guardrails,
    InputGuardrails,
    OutputGuardrails,
    BehavioralGuardrails,
    ToolDef,
)
from vasini.safety.firewall import PromptFirewall, FirewallAction

# ── Tool execution + audit + events ──────────────────────────────────────
from vasini.sandbox.executor import ToolExecutor, ToolExecutionResult
from vasini.sandbox.audit import AuditLogger
from vasini.events.bus import InMemoryEventBus
from vasini.events.envelope import CloudEvent, build_event

# ── Token accounting + budget ────────────────────────────────────────────
from vasini.finops.accounting import TokenAccounting
from vasini.finops.budget import BudgetManager, BudgetAction, BudgetStatus

# ── Eval + release ───────────────────────────────────────────────────────
from vasini.eval.scorer import QualityScorer
from vasini.eval.gate import QualityGate
from vasini.control.release import ReleaseManager, ReleaseStage

# ── Memory + GDPR ────────────────────────────────────────────────────────
from vasini.memory.manager import MemoryManager

# ── Pack registry ────────────────────────────────────────────────────────
from vasini.registry.store import PackRegistry

# ── SLO ──────────────────────────────────────────────────────────────────
from vasini.eval.slo import SLOTracker, SLOConfig, SLOStatus


# ---------------------------------------------------------------------------
# 1. Policy + Firewall pipeline
# ---------------------------------------------------------------------------


class TestPolicyFirewallPipeline:
    """PolicyEngine.from_guardrails() feeds into PromptFirewall check_input()."""

    def test_safe_input_passes_both(self):
        guardrails = Guardrails(
            input=InputGuardrails(max_length=500, jailbreak_detection=True),
            behavioral=BehavioralGuardrails(
                prohibited_actions=["rm -rf"],
                max_autonomous_steps=5,
            ),
        )

        # Policy engine evaluates context
        engine = PolicyEngine.from_guardrails(guardrails)
        decision = engine.evaluate({"input_text": "Hello, help me please", "current_step": 1})
        assert decision.is_allowed

        # Firewall checks the raw text
        firewall = PromptFirewall(input_guardrails=guardrails.input)
        result = firewall.check_input("Hello, help me please")
        assert result.passed
        assert result.action == FirewallAction.PASS

    def test_too_long_input_denied_by_both(self):
        guardrails = Guardrails(
            input=InputGuardrails(max_length=20),
            behavioral=BehavioralGuardrails(max_autonomous_steps=5),
        )
        long_text = "a" * 30

        engine = PolicyEngine.from_guardrails(guardrails)
        decision = engine.evaluate({"input_text": long_text, "current_step": 1})
        assert decision.is_denied

        firewall = PromptFirewall(input_guardrails=guardrails.input)
        result = firewall.check_input(long_text)
        assert not result.passed
        assert result.action == FirewallAction.BLOCK

    def test_prohibited_action_denied(self):
        guardrails = Guardrails(
            behavioral=BehavioralGuardrails(
                prohibited_actions=["delete_database"],
                max_autonomous_steps=10,
            ),
        )
        engine = PolicyEngine.from_guardrails(guardrails)
        decision = engine.evaluate({"action": "please delete_database now", "current_step": 1})
        assert decision.is_denied
        assert decision.verdict == PolicyVerdict.DENY


# ---------------------------------------------------------------------------
# 2. Tool execution + audit + events
# ---------------------------------------------------------------------------


class TestToolExecutionAuditEvents:
    """ToolExecutor execute -> AuditLogger entries -> EventBus publish."""

    @pytest.mark.asyncio
    async def test_execute_logs_audit_and_publishes_event(self):
        audit_logger = AuditLogger()
        executor = ToolExecutor(audit_logger=audit_logger)

        # Register a simple handler
        async def echo_handler(args: dict) -> dict:
            return {"echo": args.get("msg", "")}

        tool = ToolDef(id="echo", name="Echo Tool", audit=True)
        executor.register_handler("echo", echo_handler)

        result = await executor.execute(
            tool=tool,
            arguments={"msg": "hello"},
            tenant_id="tenant-1",
            task_id="task-42",
        )

        assert result.success
        assert result.result == {"echo": "hello"}
        assert result.duration_ms >= 0

        # Verify audit entry was created
        assert len(audit_logger.entries) == 1
        entry = audit_logger.entries[0]
        assert entry.tool_id == "echo"
        assert entry.tenant_id == "tenant-1"
        assert entry.task_id == "task-42"
        assert entry.success is True

        # Publish a completion event to EventBus
        bus = InMemoryEventBus()
        received: list[CloudEvent] = []

        async def on_tool_complete(event: CloudEvent) -> None:
            received.append(event)

        bus.subscribe("tool.execution.completed", on_tool_complete)

        event = build_event(
            event_type="tool.execution.completed",
            source="vasini/executor",
            data={"tool_id": "echo", "success": True, "duration_ms": result.duration_ms},
            tenant_id="tenant-1",
        )
        await bus.publish(event)

        assert len(received) == 1
        assert received[0].data["tool_id"] == "echo"
        assert received[0].data["success"] is True

    @pytest.mark.asyncio
    async def test_denied_tool_logged_and_fails(self):
        audit_logger = AuditLogger()
        executor = ToolExecutor(audit_logger=audit_logger)
        executor.set_denied_tools(["dangerous"])

        tool = ToolDef(id="dangerous", name="Dangerous Tool", audit=True)

        result = await executor.execute(
            tool=tool,
            arguments={},
            tenant_id="tenant-1",
            task_id="task-99",
        )

        assert not result.success
        assert "denied by policy" in result.error

        # Denied tools still get audit logged
        assert len(audit_logger.entries) == 1
        assert audit_logger.entries[0].success is False


# ---------------------------------------------------------------------------
# 3. Token accounting + budget check
# ---------------------------------------------------------------------------


class TestTokenAccountingBudget:
    """Record tokens -> estimate cost -> budget check."""

    def test_record_tokens_estimate_cost_check_budget(self):
        accounting = TokenAccounting()
        budget_mgr = BudgetManager()

        # Set pricing
        accounting.set_pricing("gpt-4", input_per_1k=0.03, output_per_1k=0.06)

        # Record usage
        accounting.record("tenant-A", "gpt-4", input_tokens=2000, output_tokens=1000)
        accounting.record("tenant-A", "gpt-4", input_tokens=3000, output_tokens=2000)

        # Verify aggregated usage
        usage = accounting.get_usage("tenant-A")
        assert usage.total_input_tokens == 5000
        assert usage.total_output_tokens == 3000

        # Estimate cost: (5000/1000)*0.03 + (3000/1000)*0.06 = 0.15 + 0.18 = 0.33
        cost = accounting.estimate_cost("tenant-A")
        assert abs(cost - 0.33) < 0.001

        # Budget check — under soft cap
        budget_mgr.set_budget("tenant-A", soft_cap=0.50, hard_cap=1.00)
        check = budget_mgr.check("tenant-A", current_spend=cost)
        assert check.action == BudgetAction.ALLOW
        assert check.status == BudgetStatus.OK

    def test_budget_hard_cap_blocks(self):
        accounting = TokenAccounting()
        budget_mgr = BudgetManager()

        accounting.set_pricing("gpt-4", input_per_1k=0.03, output_per_1k=0.06)
        accounting.record("tenant-B", "gpt-4", input_tokens=50000, output_tokens=30000)

        cost = accounting.estimate_cost("tenant-B")
        # (50000/1000)*0.03 + (30000/1000)*0.06 = 1.5 + 1.8 = 3.3
        assert cost > 3.0

        budget_mgr.set_budget("tenant-B", soft_cap=1.00, hard_cap=2.00)
        check = budget_mgr.check("tenant-B", current_spend=cost)
        assert check.action == BudgetAction.BLOCK
        assert check.status == BudgetStatus.HARD_CAP_EXCEEDED

    def test_budget_soft_cap_warns(self):
        budget_mgr = BudgetManager()
        budget_mgr.set_budget("tenant-C", soft_cap=0.50, hard_cap=1.00)
        check = budget_mgr.check("tenant-C", current_spend=0.75)
        assert check.action == BudgetAction.WARN
        assert check.status == BudgetStatus.SOFT_CAP_EXCEEDED
        assert check.remaining == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# 4. Release flow + eval gate
# ---------------------------------------------------------------------------


class TestReleaseFlowEvalGate:
    """QualityScorer score -> QualityGate evaluate -> ReleaseManager promote."""

    def test_high_quality_promotes_to_validated(self):
        scorer = QualityScorer()
        gate = QualityGate(min_score=0.85)
        release_mgr = ReleaseManager()

        # Score multiple test cases
        results = [
            scorer.score("The capital of France is Paris", "The capital of France is Paris"),
            scorer.score("hello world", "Hello World"),
        ]
        avg_score = scorer.aggregate(results)
        assert avg_score == 1.0  # both are exact matches (case-insensitive)

        # Gate evaluation
        gate_result = gate.evaluate(score=avg_score, total_cases=2, passed_cases=2)
        assert gate_result.passed
        assert gate_result.score >= gate_result.min_score

        # Promote release draft -> validated using the eval score
        release = release_mgr.create_release(pack_id="my-pack", version="1.0.0")
        assert release.stage == ReleaseStage.DRAFT

        promo = release_mgr.promote(release.id, eval_score=avg_score)
        assert promo.success
        assert promo.new_stage == ReleaseStage.VALIDATED

    def test_low_quality_blocks_promotion(self):
        scorer = QualityScorer()
        gate = QualityGate(min_score=0.85)
        release_mgr = ReleaseManager()

        # Deliberately low quality
        results = [
            scorer.score("apples", "oranges"),
            scorer.score("cats", "dogs"),
        ]
        avg_score = scorer.aggregate(results)
        assert avg_score < 0.85

        gate_result = gate.evaluate(score=avg_score, total_cases=2, passed_cases=0)
        assert not gate_result.passed

        release = release_mgr.create_release(pack_id="bad-pack", version="0.1.0")
        promo = release_mgr.promote(release.id, eval_score=avg_score)
        assert not promo.success
        assert "below minimum" in promo.reason

    def test_full_promotion_draft_to_prod(self):
        release_mgr = ReleaseManager()
        release = release_mgr.create_release(pack_id="prod-pack", version="2.0.0")

        # draft -> validated (score >= 0.85)
        promo1 = release_mgr.promote(release.id, eval_score=0.95)
        assert promo1.success
        assert promo1.new_stage == ReleaseStage.VALIDATED

        # validated -> staged
        promo2 = release_mgr.promote(release.id)
        assert promo2.success
        assert promo2.new_stage == ReleaseStage.STAGED

        # staged -> prod (requires approved_by)
        promo3 = release_mgr.promote(release.id, approved_by="platform-lead")
        assert promo3.success
        assert promo3.new_stage == ReleaseStage.PROD


# ---------------------------------------------------------------------------
# 5. Memory + GDPR
# ---------------------------------------------------------------------------


class TestMemoryGDPR:
    """MemoryManager set/write -> GDPR delete -> verify cleared."""

    def test_short_term_set_then_gdpr_delete(self):
        mgr = MemoryManager()

        # Write to short-term memory
        mgr.short_term.set("tenant-X", "agent-1", "greeting", "Hello!")
        mgr.short_term.set("tenant-X", "agent-1", "context", "Support ticket #123")

        # Verify data exists
        assert mgr.short_term.get("tenant-X", "agent-1", "greeting") == "Hello!"
        assert mgr.short_term.get("tenant-X", "agent-1", "context") == "Support ticket #123"

        # GDPR delete
        result = mgr.gdpr_delete("tenant-X")
        assert result.success
        assert result.tenant_id == "tenant-X"
        assert "short_term" in result.stores_cleared

        # Verify data is gone
        assert mgr.short_term.get("tenant-X", "agent-1", "greeting") is None
        assert mgr.short_term.get("tenant-X", "agent-1", "context") is None

    def test_factual_write_then_gdpr_delete(self):
        mgr = MemoryManager()

        # Write factual records
        mgr.factual.write(
            tenant_id="tenant-Y", agent_id="agent-1",
            key="user_preference", value="dark_mode",
            evidence="User said: I prefer dark mode", confidence=0.95,
        )
        mgr.factual.write(
            tenant_id="tenant-Y", agent_id="agent-1",
            key="language", value="English",
            evidence="User wrote in English", confidence=0.99,
        )

        # Verify data exists
        pref = mgr.factual.get_latest("tenant-Y", "agent-1", "user_preference")
        assert pref is not None
        assert pref.value == "dark_mode"

        # GDPR delete clears both stores
        result = mgr.gdpr_delete("tenant-Y")
        assert result.success
        assert "factual" in result.stores_cleared

        # Verify factual data is gone
        assert mgr.factual.get_latest("tenant-Y", "agent-1", "user_preference") is None
        assert mgr.factual.get_latest("tenant-Y", "agent-1", "language") is None

    def test_gdpr_delete_does_not_affect_other_tenants(self):
        mgr = MemoryManager()

        mgr.short_term.set("tenant-A", "agent-1", "key1", "val-A")
        mgr.short_term.set("tenant-B", "agent-1", "key1", "val-B")

        mgr.gdpr_delete("tenant-A")

        assert mgr.short_term.get("tenant-A", "agent-1", "key1") is None
        assert mgr.short_term.get("tenant-B", "agent-1", "key1") == "val-B"


# ---------------------------------------------------------------------------
# 6. Pack registry -> release flow
# ---------------------------------------------------------------------------


class TestPackRegistryReleaseFlow:
    """PackRegistry publish -> ReleaseManager create + promote."""

    def test_publish_pack_then_create_and_promote_release(self):
        registry = PackRegistry()
        release_mgr = ReleaseManager()

        manifest = {
            "schema_version": "1.0",
            "pack_id": "support-agent",
            "risk_level": "medium",
        }

        pub_result = registry.publish(
            pack_id="support-agent",
            version="1.0.0",
            manifest=manifest,
            layers={"soul": "soul.yaml", "role": "role.yaml"},
            author="dev@example.com",
        )
        assert pub_result.success
        assert pub_result.version == "1.0.0"

        # Verify artifact in registry
        artifact = registry.get("support-agent", "1.0.0")
        assert artifact is not None
        assert artifact.pack_id == "support-agent"
        assert artifact.author == "dev@example.com"

        # Create release from published pack
        release = release_mgr.create_release(
            pack_id=artifact.pack_id,
            version=artifact.version,
        )
        assert release.stage == ReleaseStage.DRAFT

        # Promote draft -> validated
        promo = release_mgr.promote(release.id, eval_score=0.92)
        assert promo.success
        assert promo.new_stage == ReleaseStage.VALIDATED

    def test_duplicate_version_rejected(self):
        registry = PackRegistry()
        manifest = {
            "schema_version": "1.0",
            "pack_id": "dup-pack",
            "risk_level": "low",
        }

        result1 = registry.publish(
            pack_id="dup-pack", version="1.0.0",
            manifest=manifest, layers={}, author="dev@test.com",
        )
        assert result1.success

        result2 = registry.publish(
            pack_id="dup-pack", version="1.0.0",
            manifest=manifest, layers={}, author="dev@test.com",
        )
        assert not result2.success
        assert "immutable" in result2.reason


# ---------------------------------------------------------------------------
# 7. SLO tracking
# ---------------------------------------------------------------------------


class TestSLOTracking:
    """SLOTracker record multiple requests -> get_report -> verify success_rate."""

    def test_slo_met_when_above_threshold(self):
        config = SLOConfig(response_p95_ms=5000, success_rate=0.98)
        tracker = SLOTracker(config=config)

        # Record 100 requests — 99 succeed, 1 fails
        for i in range(99):
            tracker.record("tenant-1", "pack-A", success=True, latency_ms=200 + i)
        tracker.record("tenant-1", "pack-A", success=False, latency_ms=300)

        report = tracker.get_report("tenant-1", "pack-A")
        assert report.total_requests == 100
        assert report.success_count == 99
        assert report.success_rate == 0.99
        assert report.slo_met is True
        assert report.status == SLOStatus.MET
        assert report.p95_latency_ms is not None
        assert report.p95_latency_ms < 5000

    def test_slo_violated_when_below_threshold(self):
        config = SLOConfig(response_p95_ms=5000, success_rate=0.98)
        tracker = SLOTracker(config=config)

        # 90 succeed, 10 fail => 90% success (below 98% threshold)
        for i in range(90):
            tracker.record("tenant-2", "pack-B", success=True, latency_ms=100)
        for i in range(10):
            tracker.record("tenant-2", "pack-B", success=False, latency_ms=100)

        report = tracker.get_report("tenant-2", "pack-B")
        assert report.total_requests == 100
        assert report.success_rate == 0.90
        assert report.slo_met is False
        assert report.status == SLOStatus.VIOLATED

    def test_slo_violated_by_high_latency(self):
        config = SLOConfig(response_p95_ms=500, success_rate=0.90)
        tracker = SLOTracker(config=config)

        # All succeed but with high latency
        for i in range(100):
            tracker.record("tenant-3", "pack-C", success=True, latency_ms=1000)

        report = tracker.get_report("tenant-3", "pack-C")
        assert report.success_rate == 1.0
        assert report.p95_latency_ms == 1000.0  # all same latency
        assert report.slo_met is False  # p95 > 500ms target
        assert report.status == SLOStatus.VIOLATED

    def test_empty_report_shows_violated(self):
        config = SLOConfig()
        tracker = SLOTracker(config=config)

        report = tracker.get_report("nobody", "nothing")
        assert report.total_requests == 0
        assert report.slo_met is False
        assert report.status == SLOStatus.VIOLATED
