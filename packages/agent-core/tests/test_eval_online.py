"""Tests for Evaluation Service — Online monitoring, SLO tracking, drift detection."""

import pytest
from vasini.eval.monitor import DriftDetector, DriftAlert, MetricPoint
from vasini.eval.slo import (
    SLOTracker, SLOConfig, SLOReport, SLOStatus,
    ShadowModeConfig,
)


class TestSLOConfig:
    def test_default_slo_config(self):
        config = SLOConfig()
        assert config.response_p95_ms == 5000
        assert config.success_rate == 0.98
        assert config.hallucination_rate == 0.08

    def test_high_risk_slo_config(self):
        config = SLOConfig(
            response_p95_ms=15000,
            success_rate=0.995,
            hallucination_rate=0.02,
        )
        assert config.success_rate == 0.995


class TestSLOTracker:
    def test_create_tracker(self):
        tracker = SLOTracker(config=SLOConfig())
        assert tracker is not None

    def test_record_success(self):
        tracker = SLOTracker(config=SLOConfig())
        tracker.record(tenant_id="t1", pack_id="pack1", success=True, latency_ms=100)
        report = tracker.get_report("t1", "pack1")
        assert report.total_requests == 1
        assert report.success_count == 1
        assert report.success_rate == 1.0

    def test_record_failure(self):
        tracker = SLOTracker(config=SLOConfig())
        tracker.record(tenant_id="t1", pack_id="pack1", success=False, latency_ms=200)
        report = tracker.get_report("t1", "pack1")
        assert report.total_requests == 1
        assert report.success_count == 0
        assert report.success_rate == 0.0

    def test_success_rate_calculation(self):
        tracker = SLOTracker(config=SLOConfig(success_rate=0.98))
        for _ in range(98):
            tracker.record("t1", "p1", success=True, latency_ms=100)
        for _ in range(2):
            tracker.record("t1", "p1", success=False, latency_ms=100)

        report = tracker.get_report("t1", "p1")
        assert report.total_requests == 100
        assert report.success_rate == 0.98
        assert report.slo_met

    def test_success_rate_below_slo(self):
        tracker = SLOTracker(config=SLOConfig(success_rate=0.98))
        for _ in range(90):
            tracker.record("t1", "p1", success=True, latency_ms=100)
        for _ in range(10):
            tracker.record("t1", "p1", success=False, latency_ms=100)

        report = tracker.get_report("t1", "p1")
        assert report.success_rate == 0.90
        assert not report.slo_met

    def test_p95_latency(self):
        tracker = SLOTracker(config=SLOConfig(response_p95_ms=5000))
        # 19 fast requests + 1 slow
        for _ in range(19):
            tracker.record("t1", "p1", success=True, latency_ms=100)
        tracker.record("t1", "p1", success=True, latency_ms=10000)

        report = tracker.get_report("t1", "p1")
        assert report.p95_latency_ms is not None
        # With 20 requests, p95 = 95th percentile
        assert report.p95_latency_ms >= 100

    def test_multi_tenant_isolation(self):
        tracker = SLOTracker(config=SLOConfig())
        tracker.record("t1", "p1", success=True, latency_ms=100)
        tracker.record("t2", "p1", success=False, latency_ms=200)

        report_t1 = tracker.get_report("t1", "p1")
        report_t2 = tracker.get_report("t2", "p1")
        assert report_t1.success_rate == 1.0
        assert report_t2.success_rate == 0.0

    def test_empty_report(self):
        tracker = SLOTracker(config=SLOConfig())
        report = tracker.get_report("unknown", "unknown")
        assert report.total_requests == 0
        assert report.success_rate == 0.0

    def test_slo_status_enum(self):
        assert SLOStatus.MET.value == "met"
        assert SLOStatus.VIOLATED.value == "violated"


class TestDriftDetector:
    def test_no_drift_with_stable_metrics(self):
        detector = DriftDetector(threshold_factor=2.0)
        baseline = [MetricPoint(value=100, timestamp=i) for i in range(10)]
        current = [MetricPoint(value=105, timestamp=i + 10) for i in range(10)]
        alert = detector.check(metric_name="latency_ms", baseline=baseline, current=current)
        assert alert is None

    def test_drift_detected_with_spike(self):
        detector = DriftDetector(threshold_factor=2.0)
        baseline = [MetricPoint(value=100, timestamp=i) for i in range(10)]
        current = [MetricPoint(value=500, timestamp=i + 10) for i in range(10)]
        alert = detector.check(metric_name="latency_ms", baseline=baseline, current=current)
        assert alert is not None
        assert alert.metric_name == "latency_ms"
        assert alert.severity in ("warning", "critical")

    def test_drift_with_degraded_success_rate(self):
        detector = DriftDetector(threshold_factor=1.5)
        baseline = [MetricPoint(value=0.99, timestamp=i) for i in range(10)]
        current = [MetricPoint(value=0.50, timestamp=i + 10) for i in range(10)]
        alert = detector.check(metric_name="success_rate", baseline=baseline, current=current)
        assert alert is not None

    def test_empty_baseline_no_alert(self):
        detector = DriftDetector()
        alert = detector.check("metric", baseline=[], current=[MetricPoint(value=100, timestamp=0)])
        assert alert is None

    def test_empty_current_no_alert(self):
        detector = DriftDetector()
        alert = detector.check("metric", baseline=[MetricPoint(value=100, timestamp=0)], current=[])
        assert alert is None


class TestShadowModeConfig:
    def test_create_shadow_config(self):
        config = ShadowModeConfig(
            enabled=True,
            traffic_percentage=10,
            shadow_pack_id="new-pack-v2",
            read_only_sandbox=True,
        )
        assert config.enabled
        assert config.traffic_percentage == 10
        assert config.read_only_sandbox

    def test_default_shadow_disabled(self):
        config = ShadowModeConfig()
        assert not config.enabled
        assert config.traffic_percentage == 0
