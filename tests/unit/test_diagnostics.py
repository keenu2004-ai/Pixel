"""Unit tests for Runtime Self-Profiling and Diagnostic Engine."""

from packages.contracts.evolution import AnomalySeverity, AnomalyType, RemediationClass
from services.evolution.diagnostics.engine import DiagnosticEngine
from services.evolution.diagnostics.profiler import RuntimeSelfProfiler


def test_runtime_self_profiler() -> None:
    profiler = RuntimeSelfProfiler(max_samples_per_metric=100)

    # Record 10 latency samples
    for i in range(1, 11):
        profiler.record_metric("pixel.agent.step_latency_ms", float(i * 10), unit="ms")

    samples = profiler.get_metric_samples("pixel.agent.step_latency_ms")
    assert len(samples) == 10

    stats = profiler.get_summary_stats("pixel.agent.step_latency_ms")
    assert stats is not None
    assert stats["count"] == 10.0
    assert stats["min"] == 10.0
    assert stats["max"] == 100.0
    assert stats["avg"] == 55.0


def test_diagnostic_engine_anomaly_detection_and_hypotheses() -> None:
    profiler = RuntimeSelfProfiler()
    engine = DiagnosticEngine(profiler)

    # Trigger high latency anomaly (threshold is 500ms)
    for _ in range(10):
        profiler.record_metric("pixel.agent.step_latency_ms", 1200.0, unit="ms")

    anomalies = engine.detect_anomalies()
    assert len(anomalies) >= 1
    lat_anom = [a for a in anomalies if a.anomaly_type == AnomalyType.HIGH_LATENCY][0]
    assert lat_anom.severity == AnomalySeverity.HIGH
    assert lat_anom.observed_value == 1200.0

    # Generate root cause hypothesis
    hypothesis = engine.diagnose_root_cause(lat_anom)
    assert hypothesis.category == "EXECUTION_BOTTLENECK"
    assert hypothesis.confidence >= 0.80

    # Generate remediation proposal
    proposal = engine.generate_remediation_proposal(hypothesis)
    assert proposal.remediation_class == RemediationClass.SWITCH_MODEL_REPLICA
    assert proposal.is_automatic_allowed is True


def test_diagnostic_engine_memory_spike_remediation() -> None:
    profiler = RuntimeSelfProfiler()
    engine = DiagnosticEngine(profiler)

    # Trigger memory spike (threshold 1024MB)
    profiler.record_metric("pixel.system.memory_mb", 2500.0, unit="MB")

    anomalies = engine.detect_anomalies()
    mem_anom = [a for a in anomalies if a.anomaly_type == AnomalyType.MEMORY_SPIKE][0]
    assert mem_anom.severity == AnomalySeverity.CRITICAL

    hypothesis = engine.diagnose_root_cause(mem_anom)
    assert hypothesis.category == "RESOURCE_EXHAUSTION"

    proposal = engine.generate_remediation_proposal(hypothesis)
    assert proposal.remediation_class == RemediationClass.CLEAR_BOUNDED_CACHE
    assert proposal.is_automatic_allowed is True
