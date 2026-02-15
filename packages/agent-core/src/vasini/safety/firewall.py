"""Prompt Firewall — input/output validation pipeline.

Input pipeline: length check -> jailbreak scan -> PII scan -> sanitize
Output pipeline: length check -> PII scan
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from vasini.models import InputGuardrails, OutputGuardrails
from vasini.safety.patterns import JailbreakDetector
from vasini.safety.pii import PIIScanner, PIIMatch


class FirewallAction(Enum):
    PASS = "pass"
    BLOCK = "block"
    WARN = "warn"
    REDACT = "redact"


@dataclass
class FirewallResult:
    passed: bool
    action: FirewallAction = FirewallAction.PASS
    reason: str = ""
    pii_matches: list[PIIMatch] = field(default_factory=list)
    sanitized_text: str | None = None


class InputCheck:
    """Validates input against InputGuardrails config."""

    def __init__(self, guardrails: InputGuardrails) -> None:
        self._guardrails = guardrails
        self._jailbreak = JailbreakDetector()
        self._pii = PIIScanner()

    def check(self, text: str) -> FirewallResult:
        # 1. Length check
        if len(text) > self._guardrails.max_length:
            return FirewallResult(
                passed=False,
                action=FirewallAction.BLOCK,
                reason=f"Input length {len(text)} exceeds max {self._guardrails.max_length}",
            )

        # 2. Jailbreak detection
        if self._guardrails.jailbreak_detection:
            scan_result = self._jailbreak.scan(text)
            if not scan_result.is_safe:
                return FirewallResult(
                    passed=False,
                    action=FirewallAction.BLOCK,
                    reason=scan_result.reason,
                )

        # 3. PII detection
        pii_matches: list[PIIMatch] = []
        sanitized: str | None = None
        if self._guardrails.pii_detection.enabled:
            pii_matches = self._pii.scan(text)
            if pii_matches:
                action_str = self._guardrails.pii_detection.action
                if action_str == "block":
                    return FirewallResult(
                        passed=False,
                        action=FirewallAction.BLOCK,
                        reason=f"PII detected: {len(pii_matches)} match(es)",
                        pii_matches=pii_matches,
                    )
                elif action_str == "redact":
                    sanitized = self._pii.redact(text)
                # "warn" falls through — passed=True with pii_matches populated

        return FirewallResult(
            passed=True,
            action=FirewallAction.PASS,
            pii_matches=pii_matches,
            sanitized_text=sanitized,
        )


class OutputCheck:
    """Validates output against OutputGuardrails config."""

    def __init__(self, guardrails: OutputGuardrails) -> None:
        self._guardrails = guardrails
        self._pii = PIIScanner()

    def check(self, text: str) -> FirewallResult:
        # 1. Length check
        if len(text) > self._guardrails.max_length:
            return FirewallResult(
                passed=False,
                action=FirewallAction.BLOCK,
                reason=f"Output length {len(text)} exceeds max {self._guardrails.max_length}",
            )

        # 2. PII check
        if self._guardrails.pii_check:
            pii_matches = self._pii.scan(text)
            if pii_matches:
                return FirewallResult(
                    passed=False,
                    action=FirewallAction.BLOCK,
                    reason=f"PII detected in output: {len(pii_matches)} match(es)",
                    pii_matches=pii_matches,
                )

        return FirewallResult(passed=True)


class PromptFirewall:
    """Top-level firewall combining input and output checks."""

    def __init__(
        self,
        input_guardrails: InputGuardrails | None = None,
        output_guardrails: OutputGuardrails | None = None,
    ) -> None:
        self._input_check = InputCheck(input_guardrails or InputGuardrails())
        self._output_check = OutputCheck(output_guardrails or OutputGuardrails())

    def check_input(self, text: str) -> FirewallResult:
        return self._input_check.check(text)

    def check_output(self, text: str) -> FirewallResult:
        return self._output_check.check(text)
