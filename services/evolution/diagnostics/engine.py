"""PIXEL — Diagnostic Engine.

Detects runtime anomalies, collects evidence, computes root-cause hypotheses,
and generates structured remediation proposals.
"""

import uuid
from datetime import UTC, datetime

from packages.contracts.evolution import (
    AnomalySeverity,
    AnomalyType,
    DiagnosticAnomaly,
    RemediationClass,
    RemediationProposal,
    RootCauseHypothesis,
)
from services.evolution.diagnostics.profiler import RuntimeSelfProfiler


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class DiagnosticEngine:
    """Analyzes runtime telemetry, isolates anomalies, and formulates remediation proposals."""

    def __init__(self, profiler: RuntimeSelfProfiler) -> None:
        self.profiler = profiler
        self._thresholds: dict[AnomalyType, float] = {
            AnomalyType.HIGH_LATENCY: 500.0,  # ms
            AnomalyType.MEMORY_SPIKE: 1024.0,  # MB
            AnomalyType.TASK_FAILURE_SPIKE: 0.10,  # 10% error rate
            AnomalyType.POLICY_DENIAL_SURGE: 5.0,  # count in window
            AnomalyType.MODEL_DRIFT: 0.25,  # drift score
            AnomalyType.SYNC_LAG: 5000.0,  # ms lag
            AnomalyType.TOOL_TIMEOUT: 3.0,  # timeouts in window
        }
        self._anomalies: list[DiagnosticAnomaly] = []
        self._hypotheses: dict[str, RootCauseHypothesis] = {}
        self._proposals: dict[str, RemediationProposal] = {}

    def set_threshold(self, anomaly_type: AnomalyType, threshold: float) -> None:
        """Configures alert threshold for a specific anomaly type."""
        self._thresholds[anomaly_type] = threshold

    def detect_anomalies(self) -> list[DiagnosticAnomaly]:
        """Scans current profile metrics against defined thresholds."""
        new_anomalies: list[DiagnosticAnomaly] = []

        # 1. Latency check
        latency_stats = self.profiler.get_summary_stats("pixel.agent.step_latency_ms")
        if latency_stats and latency_stats["p95"] > self._thresholds[AnomalyType.HIGH_LATENCY]:
            anom = DiagnosticAnomaly(
                anomaly_id=f"anom-lat-{uuid.uuid4().hex[:8]}",
                anomaly_type=AnomalyType.HIGH_LATENCY,
                severity=AnomalySeverity.HIGH
                if latency_stats["p95"] > 1000.0
                else AnomalySeverity.MEDIUM,
                observed_value=latency_stats["p95"],
                threshold=self._thresholds[AnomalyType.HIGH_LATENCY],
                evidence={"stats": latency_stats},
                detected_at=_utc_now_iso(),
            )
            new_anomalies.append(anom)
            self._anomalies.append(anom)

        # 2. Memory check
        mem_stats = self.profiler.get_summary_stats("pixel.system.memory_mb")
        if mem_stats and mem_stats["max"] > self._thresholds[AnomalyType.MEMORY_SPIKE]:
            anom = DiagnosticAnomaly(
                anomaly_id=f"anom-mem-{uuid.uuid4().hex[:8]}",
                anomaly_type=AnomalyType.MEMORY_SPIKE,
                severity=AnomalySeverity.CRITICAL
                if mem_stats["max"] > 2048.0
                else AnomalySeverity.HIGH,
                observed_value=mem_stats["max"],
                threshold=self._thresholds[AnomalyType.MEMORY_SPIKE],
                evidence={"stats": mem_stats},
                detected_at=_utc_now_iso(),
            )
            new_anomalies.append(anom)
            self._anomalies.append(anom)

        # 3. Sync lag check
        sync_stats = self.profiler.get_summary_stats("pixel.mesh.sync_lag_ms")
        if sync_stats and sync_stats["max"] > self._thresholds[AnomalyType.SYNC_LAG]:
            anom = DiagnosticAnomaly(
                anomaly_id=f"anom-sync-{uuid.uuid4().hex[:8]}",
                anomaly_type=AnomalyType.SYNC_LAG,
                severity=AnomalySeverity.MEDIUM,
                observed_value=sync_stats["max"],
                threshold=self._thresholds[AnomalyType.SYNC_LAG],
                evidence={"stats": sync_stats},
                detected_at=_utc_now_iso(),
            )
            new_anomalies.append(anom)
            self._anomalies.append(anom)

        return new_anomalies

    def diagnose_root_cause(self, anomaly: DiagnosticAnomaly) -> RootCauseHypothesis:
        """Formulates an explainable root-cause hypothesis from an observed anomaly."""
        hypo_id = f"hypo-{uuid.uuid4().hex[:8]}"

        if anomaly.anomaly_type == AnomalyType.HIGH_LATENCY:
            hypothesis = RootCauseHypothesis(
                hypothesis_id=hypo_id,
                anomaly_id=anomaly.anomaly_id,
                category="EXECUTION_BOTTLENECK",
                explanation=f"Agent step P95 latency ({anomaly.observed_value:.1f}ms) exceeds SLA ({anomaly.threshold:.1f}ms). Possible unindexed vector query or slow model inference.",
                confidence=0.85,
                affected_components=["services.agent.runtime", "services.memory.stores"],
            )
        elif anomaly.anomaly_type == AnomalyType.MEMORY_SPIKE:
            hypothesis = RootCauseHypothesis(
                hypothesis_id=hypo_id,
                anomaly_id=anomaly.anomaly_id,
                category="RESOURCE_EXHAUSTION",
                explanation=f"Process memory ({anomaly.observed_value:.1f}MB) exceeded ceiling ({anomaly.threshold:.1f}MB). Cache growth or unbounded buffer accumulation suspected.",
                confidence=0.90,
                affected_components=["services.ecosystem.sandbox", "services.control_plane.server"],
            )
        elif anomaly.anomaly_type == AnomalyType.SYNC_LAG:
            hypothesis = RootCauseHypothesis(
                hypothesis_id=hypo_id,
                anomaly_id=anomaly.anomaly_id,
                category="NETWORK_PARTITION",
                explanation=f"Memory mesh synchronization lag ({anomaly.observed_value:.1f}ms) indicates transient network disconnect or satellite queue congestion.",
                confidence=0.75,
                affected_components=["services.evolution.memory_mesh"],
            )
        else:
            hypothesis = RootCauseHypothesis(
                hypothesis_id=hypo_id,
                anomaly_id=anomaly.anomaly_id,
                category="UNCLASSIFIED_FAULT",
                explanation=f"Anomaly {anomaly.anomaly_type.value} observed at value {anomaly.observed_value}.",
                confidence=0.50,
                affected_components=["pixel.core"],
            )

        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        return hypothesis

    def generate_remediation_proposal(
        self,
        hypothesis: RootCauseHypothesis,
    ) -> RemediationProposal:
        """Generates candidate remediation proposal conforming to the safe remediation allowlist."""
        prop_id = f"rem-{uuid.uuid4().hex[:8]}"

        # Map hypothesis category to allowlisted remediation
        if hypothesis.category == "RESOURCE_EXHAUSTION":
            remediation = RemediationProposal(
                proposal_id=prop_id,
                anomaly_id=hypothesis.anomaly_id,
                hypothesis_id=hypothesis.hypothesis_id,
                remediation_class=RemediationClass.CLEAR_BOUNDED_CACHE,
                is_automatic_allowed=True,
                parameters={"target_cache": "query_cache", "flush_size_percent": 50},
                risk_class="REVERSIBLE_WRITE",
            )
        elif hypothesis.category == "NETWORK_PARTITION":
            remediation = RemediationProposal(
                proposal_id=prop_id,
                anomaly_id=hypothesis.anomaly_id,
                hypothesis_id=hypothesis.hypothesis_id,
                remediation_class=RemediationClass.RETRY_TRANSIENT,
                is_automatic_allowed=True,
                parameters={"backoff_seconds": 2.0, "max_retries": 3},
                risk_class="REVERSIBLE_WRITE",
            )
        elif hypothesis.category == "EXECUTION_BOTTLENECK":
            remediation = RemediationProposal(
                proposal_id=prop_id,
                anomaly_id=hypothesis.anomaly_id,
                hypothesis_id=hypothesis.hypothesis_id,
                remediation_class=RemediationClass.SWITCH_MODEL_REPLICA,
                is_automatic_allowed=True,
                parameters={"target_replica": "local_qwen_fast"},
                risk_class="REVERSIBLE_WRITE",
            )
        else:
            # Code or structural modifications strictly require human approval
            remediation = RemediationProposal(
                proposal_id=prop_id,
                anomaly_id=hypothesis.anomaly_id,
                hypothesis_id=hypothesis.hypothesis_id,
                remediation_class=RemediationClass.PROPOSE_CODE_PATCH,
                is_automatic_allowed=False,
                parameters={"requires_operator_review": True},
                risk_class="HIGH_IMPACT",
            )

        self._proposals[remediation.proposal_id] = remediation
        return remediation
