"""Quality gate — pass/fail decision based on score threshold.

Default min_score: 0.85 (from design doc).
CI integration: gate returns GateResult with passed=True/False.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateResult:
    passed: bool
    score: float
    min_score: float
    total_cases: int
    passed_cases: int


class QualityGate:
    """Evaluates whether quality score meets threshold."""

    def __init__(self, min_score: float = 0.85) -> None:
        self.min_score = min_score

    def evaluate(self, score: float, total_cases: int, passed_cases: int) -> GateResult:
        return GateResult(
            passed=score >= self.min_score,
            score=score,
            min_score=self.min_score,
            total_cases=total_cases,
            passed_cases=passed_cases,
        )
