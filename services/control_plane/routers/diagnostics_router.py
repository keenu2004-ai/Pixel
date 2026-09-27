"""Control Plane Diagnostics and Self-Profiling API Router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.evolution import (
    DiagnosticAnomaly,
    RemediationProposal,
    SystemProfileMetric,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    get_current_user,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/diagnostics", tags=["Diagnostics & Profiling"])


@router.get("/metrics", response_model=list[SystemProfileMetric])
async def get_metrics(
    metric_name: Annotated[str, Query(description="Metric name to query")],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(get_current_user)],
    limit: int = 100,
) -> list[SystemProfileMetric]:
    """Retrieves recent telemetry samples for a specific metric."""
    return manager.runtime_profiler.get_metric_samples(metric_name, limit=limit)


@router.get("/metrics/summary", response_model=dict[str, Any])
async def get_metric_summary(
    metric_name: Annotated[str, Query(description="Metric name to summarize")],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(get_current_user)],
) -> dict[str, Any]:
    """Calculates summary statistics (min, max, avg, p95) for a metric."""
    stats = manager.runtime_profiler.get_summary_stats(metric_name)
    if not stats:
        return {"metric_name": metric_name, "count": 0}
    return {"metric_name": metric_name, **stats}


@router.post("/anomalies/scan", response_model=list[DiagnosticAnomaly])
async def scan_anomalies(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> list[DiagnosticAnomaly]:
    """Scans current telemetry against thresholds and detects anomalies."""
    return manager.diagnostic_engine.detect_anomalies()


@router.post("/remediations/propose", response_model=RemediationProposal)
async def generate_remediation_for_anomaly(
    anomaly: DiagnosticAnomaly,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> RemediationProposal:
    """Diagnoses root cause and formulates candidate remediation proposal."""
    hypothesis = manager.diagnostic_engine.diagnose_root_cause(anomaly)
    return manager.diagnostic_engine.generate_remediation_proposal(hypothesis)
