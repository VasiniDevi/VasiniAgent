"""SLO tracker — per tenant+pack success rate, latency percentiles.

SLO targets by risk level (from design doc):
  low:    p95 < 5s,  success > 98%,   hallucination < 8%
  medium: p95 < 8s,  success > 99%,   hallucination < 5%
  high:   p95 < 15s, success > 99.5%, hallucination < 2%

Error budget: 30d window. Exhaustion → freeze rollouts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class SLOStatus(Enum):
    MET = "met"
    VIOLATED = "violated"


@dataclass
class SLOConfig:
    response_p95_ms: int = 5000
    success_rate: float = 0.98
    hallucination_rate: float = 0.08
    error_budget_window_days: int = 30


@dataclass
class SLOReport:
    tenant_id: str
    pack_id: str
    total_requests: int
    success_count: int
    success_rate: float
    p95_latency_ms: float | None
    slo_met: bool
    status: SLOStatus = SLOStatus.MET


@dataclass
class ShadowModeConfig:
    """Shadow mode configuration — data model only (execution in Phase 4)."""
    enabled: bool = False
    traffic_percentage: int = 0
    shadow_pack_id: str = ""
    read_only_sandbox: bool = True


@dataclass
class _TenantMetrics:
    successes: int = 0
    failures: int = 0
    latencies: list[int] = field(default_factory=list)


class SLOTracker:
    """Tracks SLO metrics per tenant+pack."""

    def __init__(self, config: SLOConfig) -> None:
        self.config = config
        self._metrics: dict[str, _TenantMetrics] = {}

    def _key(self, tenant_id: str, pack_id: str) -> str:
        return f"{tenant_id}:{pack_id}"

    def record(self, tenant_id: str, pack_id: str, success: bool, latency_ms: int) -> None:
        key = self._key(tenant_id, pack_id)
        if key not in self._metrics:
            self._metrics[key] = _TenantMetrics()
        m = self._metrics[key]
        if success:
            m.successes += 1
        else:
            m.failures += 1
        m.latencies.append(latency_ms)

    def get_report(self, tenant_id: str, pack_id: str) -> SLOReport:
        key = self._key(tenant_id, pack_id)
        m = self._metrics.get(key)
        if not m:
            return SLOReport(
                tenant_id=tenant_id, pack_id=pack_id,
                total_requests=0, success_count=0,
                success_rate=0.0, p95_latency_ms=None,
                slo_met=False, status=SLOStatus.VIOLATED,
            )

        total = m.successes + m.failures
        rate = m.successes / total if total > 0 else 0.0
        p95 = self._percentile(m.latencies, 95) if m.latencies else None

        slo_met = rate >= self.config.success_rate
        if p95 is not None and p95 > self.config.response_p95_ms:
            slo_met = False

        return SLOReport(
            tenant_id=tenant_id, pack_id=pack_id,
            total_requests=total, success_count=m.successes,
            success_rate=rate, p95_latency_ms=p95,
            slo_met=slo_met,
            status=SLOStatus.MET if slo_met else SLOStatus.VIOLATED,
        )

    @staticmethod
    def _percentile(data: list[int], pct: int) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (pct / 100) * (len(sorted_data) - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(sorted_data[int(k)])
        return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)
