"""Policy rules — individual evaluatable conditions.

Each rule returns PolicyDecision: ALLOW, DENY, or PENDING_APPROVAL.
Rules are composable and loaded from pack's Guardrails layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class PolicyVerdict(Enum):
    ALLOW = "allow"
    DENY = "deny"
    PENDING_APPROVAL = "pending_approval"


@dataclass
class PolicyDecision:
    verdict: PolicyVerdict = PolicyVerdict.ALLOW
    reason: str = ""
    rule_id: str = ""

    @property
    def is_allowed(self) -> bool:
        return self.verdict == PolicyVerdict.ALLOW

    @property
    def is_denied(self) -> bool:
        return self.verdict == PolicyVerdict.DENY


class Rule(ABC):
    """Base class for all policy rules."""

    @abstractmethod
    def evaluate(self, context: dict) -> PolicyDecision:
        ...


@dataclass
class RuleSet:
    """Named collection of rules."""
    name: str
    rules: list[Rule] = field(default_factory=list)


class InputLengthRule(Rule):
    def __init__(self, max_length: int) -> None:
        self.max_length = max_length

    def evaluate(self, context: dict) -> PolicyDecision:
        input_text = context.get("input_text", "")
        if len(input_text) > self.max_length:
            return PolicyDecision(
                verdict=PolicyVerdict.DENY,
                reason=f"Input length {len(input_text)} exceeds max {self.max_length}",
                rule_id="input_length",
            )
        return PolicyDecision()


class ProhibitedActionRule(Rule):
    def __init__(self, prohibited: list[str]) -> None:
        self.prohibited = prohibited

    def evaluate(self, context: dict) -> PolicyDecision:
        action = context.get("action", "")
        for p in self.prohibited:
            if p in action:
                return PolicyDecision(
                    verdict=PolicyVerdict.DENY,
                    reason=f"Action contains prohibited pattern: {p}",
                    rule_id="prohibited_actions",
                )
        return PolicyDecision()


class RiskLevelRule(Rule):
    def __init__(self, require_approval_for: list[str] | None = None) -> None:
        self.require_approval_for = require_approval_for or ["high"]

    def evaluate(self, context: dict) -> PolicyDecision:
        risk_level = context.get("risk_level", "low")
        if risk_level in self.require_approval_for:
            return PolicyDecision(
                verdict=PolicyVerdict.PENDING_APPROVAL,
                reason=f"Risk level '{risk_level}' requires human approval",
                rule_id="risk_level",
            )
        return PolicyDecision()


class MaxStepsRule(Rule):
    def __init__(self, max_steps: int) -> None:
        self.max_steps = max_steps

    def evaluate(self, context: dict) -> PolicyDecision:
        current_step = context.get("current_step", 0)
        if current_step > self.max_steps:
            return PolicyDecision(
                verdict=PolicyVerdict.DENY,
                reason=f"Step {current_step} exceeds max {self.max_steps}",
                rule_id="max_steps",
            )
        return PolicyDecision()


class ActionRule(Rule):
    """Generic action-based rule (for extensibility)."""
    def __init__(self, action_pattern: str, verdict: PolicyVerdict = PolicyVerdict.DENY, reason: str = "") -> None:
        self.action_pattern = action_pattern
        self._verdict = verdict
        self._reason = reason

    def evaluate(self, context: dict) -> PolicyDecision:
        action = context.get("action", "")
        if self.action_pattern in action:
            return PolicyDecision(
                verdict=self._verdict,
                reason=self._reason or f"Action matched pattern: {self.action_pattern}",
                rule_id="action_rule",
            )
        return PolicyDecision()
