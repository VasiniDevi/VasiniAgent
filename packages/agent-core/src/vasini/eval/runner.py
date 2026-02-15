"""Evaluation runner — executes agent against golden dataset entries."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable


@dataclass
class EvalCase:
    id: str
    input: str
    expected_output: str
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class EvalResult:
    case_id: str
    actual_output: str
    expected_output: str
    duration_ms: int = 0
    error: str | None = None


AgentFn = Callable[[str], Awaitable[str]]


class EvalRunner:
    """Runs evaluation cases against an agent function."""

    def __init__(self, agent_fn: AgentFn) -> None:
        self._agent_fn = agent_fn

    async def run_case(self, case: EvalCase) -> EvalResult:
        start = time.monotonic()
        try:
            actual = await self._agent_fn(case.input)
            duration = int((time.monotonic() - start) * 1000)
            return EvalResult(
                case_id=case.id,
                actual_output=actual,
                expected_output=case.expected_output,
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return EvalResult(
                case_id=case.id,
                actual_output="",
                expected_output=case.expected_output,
                duration_ms=duration,
                error=str(e),
            )

    async def run_dataset(self, cases: list[EvalCase]) -> list[EvalResult]:
        results = []
        for case in cases:
            result = await self.run_case(case)
            results.append(result)
        return results
