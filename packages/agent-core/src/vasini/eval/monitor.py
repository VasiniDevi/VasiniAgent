"""Drift detection — compares rolling window metrics against baseline.

Detects quality degradation, latency spikes, cost anomalies.
Simple approach: compare mean of current window vs baseline.
Alert if current deviates by > threshold_factor.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MetricPoint:
    value: float
    timestamp: float


@dataclass
class DriftAlert:
    metric_name: str
    baseline_mean: float
    current_mean: float
    deviation_factor: float
    severity: str  # "warning" | "critical"


class DriftDetector:
    """Detect metric drift between baseline and current windows."""

    def __init__(self, threshold_factor: float = 2.0) -> None:
        self.threshold_factor = threshold_factor

    def check(
        self,
        metric_name: str,
        baseline: list[MetricPoint],
        current: list[MetricPoint],
    ) -> DriftAlert | None:
        if not baseline or not current:
            return None

        baseline_mean = sum(p.value for p in baseline) / len(baseline)
        current_mean = sum(p.value for p in current) / len(current)

        if baseline_mean == 0:
            return None

        # For rate metrics (0-1 range), use ratio of max/min to detect degradation
        if 0 < baseline_mean <= 1 and 0 < current_mean <= 1:
            deviation = max(baseline_mean, current_mean) / min(baseline_mean, current_mean)
        else:
            deviation = abs(current_mean - baseline_mean) / abs(baseline_mean)

        if deviation >= self.threshold_factor:
            severity = "critical" if deviation >= self.threshold_factor * 2 else "warning"
            return DriftAlert(
                metric_name=metric_name,
                baseline_mean=baseline_mean,
                current_mean=current_mean,
                deviation_factor=deviation,
                severity=severity,
            )
        return None
