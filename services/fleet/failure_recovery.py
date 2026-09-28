"""PIXEL — Phase 17 Fleet Failure Recovery & Partition Coordinator.

Handles node failure detection, stale lease reclamation, checkpoint resumption,
network partition recovery, and malicious node isolation.
"""

from typing import Any

from services.fleet.node_manager import EdgeNodeManager
from services.fleet.scheduler import FleetScheduler


class FleetFailureRecoveryEngine:
    """Detects and mitigates edge node failures, partitions, and anomalies."""

    def __init__(
        self,
        node_manager: EdgeNodeManager,
        scheduler: FleetScheduler,
    ) -> None:
        self._node_manager = node_manager
        self._scheduler = scheduler

    def recover_failed_node_tasks(self, failed_node_id: str) -> list[dict[str, Any]]:
        """Reclaims leases and resumes tasks from latest checkpoints after node failure."""
        recovered: list[dict[str, Any]] = []

        for task_id, lease in list(self._scheduler._leases.items()):
            if lease.node_id == failed_node_id and lease.is_active:
                # 1. Revoke stale lease
                lease.is_active = False

                # 2. Get latest checkpoint
                cp = self._scheduler.get_latest_checkpoint(task_id)

                # 3. Mark for rescheduling
                recovered.append(
                    {
                        "task_id": task_id,
                        "failed_node": failed_node_id,
                        "resumed_step": cp.step_number if cp else 0,
                        "checkpoint_state": cp.state_payload if cp else {},
                    }
                )

        return recovered

    def detect_and_isolate_malicious_node(
        self,
        node_id: str,
        violation_type: str,
    ) -> bool:
        """Quarantines node and halts all active delegated tasks."""
        quarantined = self._node_manager.quarantine_node(
            node_id=node_id,
            reason=f"Security violation detected: {violation_type}",
        )
        if quarantined:
            # Cancel all tasks currently leased to this node
            for task_id, lease in list(self._scheduler._leases.items()):
                if lease.node_id == node_id and lease.is_active:
                    self._scheduler.cancel_task(task_id)
            return True
        return False
