"""Policy Engine — evaluates rules against request context.

First non-ALLOW verdict wins (short-circuit):
  DENY → stop, return DENY
  PENDING_APPROVAL → stop, return PENDING_APPROVAL
  ALLOW → continue to next rule

If all rules ALLOW → final verdict is ALLOW.

Pluggable: OPA adapter can replace this engine without changing callers.
"""

from __future__ import annotations

from vasini.policy.rules import (
    Rule, PolicyDecision, PolicyVerdict,
    InputLengthRule, ProhibitedActionRule, MaxStepsRule,
)


class PolicyEngine:
    def __init__(self) -> None:
        self._rules: list[Rule] = []

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def evaluate(self, context: dict) -> PolicyDecision:
        for rule in self._rules:
            decision = rule.evaluate(context)
            if decision.verdict != PolicyVerdict.ALLOW:
                return decision
        return PolicyDecision(verdict=PolicyVerdict.ALLOW)

    @classmethod
    def from_guardrails(cls, guardrails) -> PolicyEngine:
        """Build engine from pack's Guardrails model."""
        engine = cls()
        engine.add_rule(InputLengthRule(max_length=guardrails.input.max_length))
        if guardrails.behavioral.prohibited_actions:
            engine.add_rule(ProhibitedActionRule(
                prohibited=guardrails.behavioral.prohibited_actions
            ))
        engine.add_rule(MaxStepsRule(max_steps=guardrails.behavioral.max_autonomous_steps))
        return engine
