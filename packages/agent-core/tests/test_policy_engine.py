"""Tests for Policy Engine — runtime enforcement of guardrails."""

import pytest
from vasini.policy.engine import PolicyEngine, PolicyDecision, PolicyVerdict
from vasini.policy.rules import (
    Rule, RuleSet, ActionRule, InputLengthRule, ProhibitedActionRule,
    RiskLevelRule, MaxStepsRule,
)
from vasini.models import Guardrails, InputGuardrails, BehavioralGuardrails


class TestPolicyDecision:
    def test_allow_decision(self):
        decision = PolicyDecision(verdict=PolicyVerdict.ALLOW)
        assert decision.is_allowed
        assert not decision.is_denied

    def test_deny_decision(self):
        decision = PolicyDecision(
            verdict=PolicyVerdict.DENY,
            reason="Prohibited action: rm -rf",
            rule_id="prohibited_actions",
        )
        assert decision.is_denied
        assert not decision.is_allowed
        assert "rm -rf" in decision.reason

    def test_pending_approval_decision(self):
        decision = PolicyDecision(
            verdict=PolicyVerdict.PENDING_APPROVAL,
            reason="High-risk action requires human approval",
            rule_id="risk_level",
        )
        assert not decision.is_allowed
        assert not decision.is_denied
        assert decision.verdict == PolicyVerdict.PENDING_APPROVAL


class TestRules:
    def test_input_length_rule_allows_short_input(self):
        rule = InputLengthRule(max_length=1000)
        ctx = {"input_text": "Hello world"}
        result = rule.evaluate(ctx)
        assert result.is_allowed

    def test_input_length_rule_denies_long_input(self):
        rule = InputLengthRule(max_length=10)
        ctx = {"input_text": "This is a very long input exceeding limit"}
        result = rule.evaluate(ctx)
        assert result.is_denied
        assert "length" in result.reason.lower()

    def test_prohibited_action_denies_match(self):
        rule = ProhibitedActionRule(prohibited=["rm -rf", "DROP TABLE"])
        ctx = {"action": "rm -rf /"}
        result = rule.evaluate(ctx)
        assert result.is_denied

    def test_prohibited_action_allows_safe(self):
        rule = ProhibitedActionRule(prohibited=["rm -rf", "DROP TABLE"])
        ctx = {"action": "ls -la"}
        result = rule.evaluate(ctx)
        assert result.is_allowed

    def test_risk_level_high_requires_approval(self):
        rule = RiskLevelRule(require_approval_for=["high"])
        ctx = {"risk_level": "high", "action": "execute_code"}
        result = rule.evaluate(ctx)
        assert result.verdict == PolicyVerdict.PENDING_APPROVAL

    def test_risk_level_low_allows(self):
        rule = RiskLevelRule(require_approval_for=["high"])
        ctx = {"risk_level": "low", "action": "search"}
        result = rule.evaluate(ctx)
        assert result.is_allowed

    def test_max_steps_denies_exceeded(self):
        rule = MaxStepsRule(max_steps=10)
        ctx = {"current_step": 11}
        result = rule.evaluate(ctx)
        assert result.is_denied

    def test_max_steps_allows_within(self):
        rule = MaxStepsRule(max_steps=10)
        ctx = {"current_step": 5}
        result = rule.evaluate(ctx)
        assert result.is_allowed


class TestPolicyEngine:
    def test_create_engine(self):
        engine = PolicyEngine()
        assert engine is not None

    def test_empty_engine_allows_all(self):
        engine = PolicyEngine()
        result = engine.evaluate({"action": "anything"})
        assert result.is_allowed

    def test_engine_with_deny_rule(self):
        engine = PolicyEngine()
        engine.add_rule(ProhibitedActionRule(prohibited=["dangerous"]))
        result = engine.evaluate({"action": "dangerous operation"})
        assert result.is_denied

    def test_engine_first_deny_wins(self):
        """Multiple rules: first DENY short-circuits."""
        engine = PolicyEngine()
        engine.add_rule(InputLengthRule(max_length=5))
        engine.add_rule(ProhibitedActionRule(prohibited=["test"]))
        result = engine.evaluate({"input_text": "very long input", "action": "safe"})
        assert result.is_denied
        assert "length" in result.reason.lower()

    def test_engine_from_guardrails(self):
        """Build engine from pack's Guardrails model."""
        guardrails = Guardrails(
            input=InputGuardrails(max_length=100),
            behavioral=BehavioralGuardrails(
                prohibited_actions=["shell_exec", "network_scan"],
                max_autonomous_steps=5,
            ),
        )
        engine = PolicyEngine.from_guardrails(guardrails)
        # Input too long
        result = engine.evaluate({"input_text": "x" * 200})
        assert result.is_denied
        # Prohibited action
        result = engine.evaluate({"input_text": "ok", "action": "shell_exec"})
        assert result.is_denied
        # Max steps exceeded
        result = engine.evaluate({"input_text": "ok", "action": "safe", "current_step": 6})
        assert result.is_denied
        # All good
        result = engine.evaluate({"input_text": "ok", "action": "safe", "current_step": 3})
        assert result.is_allowed

    def test_pending_approval_stops_evaluation(self):
        """PENDING_APPROVAL is returned immediately (doesn't continue to next rule)."""
        engine = PolicyEngine()
        engine.add_rule(RiskLevelRule(require_approval_for=["high"]))
        engine.add_rule(ProhibitedActionRule(prohibited=["test"]))
        result = engine.evaluate({"risk_level": "high", "action": "test"})
        assert result.verdict == PolicyVerdict.PENDING_APPROVAL
