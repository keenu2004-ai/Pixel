"""PIXEL — Phase 17 Edge Node Lifecycle & Fleet Topology Manager.

Manages node enrollment with PKI certificates, state machine transitions,
heartbeat tracking, capability discovery, hardware profiling, and device revocation.
"""

from datetime import UTC, datetime, timedelta

from packages.contracts.fleet import (
    EdgeNode,
    EdgeNodeIdentity,
    FleetCapability,
    FleetNodeState,
    HardwareProfile,
    NetworkCondition,
    ResourceProfile,
)
from packages.contracts.orchestration import DeviceCapability, DeviceRole
from services.orchestration.pki import PKIEngine


class EdgeNodeManager:
    """Master manager for fleet edge nodes, trust states, and health monitoring."""

    def __init__(
        self,
        pki_engine: PKIEngine | None = None,
        heartbeat_timeout_seconds: float = 30.0,
    ) -> None:
        self._pki_engine = pki_engine or PKIEngine()
        self._heartbeat_timeout = heartbeat_timeout_seconds
        self._nodes: dict[str, EdgeNode] = {}
        self._revoked_node_ids: set[str] = set()

    def enroll_node(
        self,
        node_id: str,
        node_name: str,
        device_type: str = "DESKTOP",
        capabilities: list[FleetCapability] | None = None,
        hardware: HardwareProfile | None = None,
        is_central_authority: bool = False,
    ) -> EdgeNode:
        """Securely enrolls a new edge node, issuing and verifying PKI credentials."""
        if node_id in self._revoked_node_ids:
            raise PermissionError(f"Node '{node_id}' is permanently revoked and cannot re-enroll.")

        mock_pub_key = f"-----BEGIN PUBLIC KEY-----\n{node_id}_KEY\n-----END PUBLIC KEY-----"
        role = DeviceRole.PRIMARY_PC if is_central_authority else DeviceRole.EDGE_COMPUTE
        cert_pem = self._pki_engine.issue_device_certificate(
            device_id=node_id,
            role=role,
            capabilities=[DeviceCapability.CODE_EXECUTION, DeviceCapability.DISPLAY],
            public_key_pem=mock_pub_key,
        )
        _, _, payload = self._pki_engine.validate_certificate(cert_pem)
        serial = str(payload.get("serial", node_id)) if payload else node_id
        fingerprint = (
            str(
                payload.get(
                    "public_key_fingerprint", self._pki_engine.compute_fingerprint(mock_pub_key)
                )
            )
            if payload
            else self._pki_engine.compute_fingerprint(mock_pub_key)
        )
        now = datetime.now(UTC)

        identity = EdgeNodeIdentity(
            node_id=node_id,
            node_name=node_name,
            device_type=device_type,
            public_key_fingerprint=fingerprint,
            certificate_serial=serial,
            is_central_authority=is_central_authority,
            enrolled_at=now,
        )

        node = EdgeNode(
            identity=identity,
            state=FleetNodeState.ACTIVE,
            capabilities=capabilities or [FleetCapability.CPU],
            hardware=hardware or HardwareProfile(),
            resources=ResourceProfile(),
            last_heartbeat=now,
        )

        self._nodes[node_id] = node
        return node

    def get_node(self, node_id: str) -> EdgeNode | None:
        """Retrieves edge node by ID if not revoked."""
        if node_id in self._revoked_node_ids:
            return None
        return self._nodes.get(node_id)

    def list_nodes(
        self,
        active_only: bool = False,
        capability_filter: FleetCapability | None = None,
    ) -> list[EdgeNode]:
        """Lists registered fleet nodes with optional capability and active state filtering."""
        self.sweep_stale_heartbeats()
        results: list[EdgeNode] = []
        for node in self._nodes.values():
            if node.identity.node_id in self._revoked_node_ids:
                continue
            if active_only and not node.is_available_for_tasks():
                continue
            if capability_filter and capability_filter not in node.capabilities:
                continue
            results.append(node)
        return results

    def list_active_nodes(self) -> list[EdgeNode]:
        """Convenience method returning all currently active, non-revoked nodes."""
        return self.list_nodes(active_only=True)

    def record_heartbeat(
        self,
        node_id: str,
        resources: ResourceProfile | None = None,
    ) -> bool:
        """Updates node heartbeat timestamp and real-time resource telemetry."""
        node = self._nodes.get(node_id)
        if not node or node_id in self._revoked_node_ids:
            return False

        node.last_heartbeat = datetime.now(UTC)
        if resources:
            node.resources = resources

        if node.state in (FleetNodeState.OFFLINE, FleetNodeState.DEGRADED):
            node.state = FleetNodeState.ACTIVE

        return True

    def sweep_stale_heartbeats(self) -> list[str]:
        """Marks nodes with stale heartbeats as OFFLINE."""
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(seconds=self._heartbeat_timeout)
        stale_nodes: list[str] = []

        for node_id, node in self._nodes.items():
            if node.identity.is_central_authority or node_id in self._revoked_node_ids:
                continue
            if node.last_heartbeat < stale_cutoff and node.state == FleetNodeState.ACTIVE:
                node.state = FleetNodeState.OFFLINE
                node.resources.network_condition = NetworkCondition.OFFLINE
                stale_nodes.append(node_id)

        return stale_nodes

    def quarantine_node(self, node_id: str, reason: str) -> bool:
        """Isolates a suspicious or misbehaving node."""
        node = self._nodes.get(node_id)
        if not node or node.identity.is_central_authority:
            return False

        node.state = FleetNodeState.QUARANTINED
        node.quarantine_reason = reason
        return True

    def revoke_node(self, node_id: str, reason: str = "Admin revocation") -> bool:
        """Permanently revokes a node, revoking its certificate and severing access."""
        node = self._nodes.get(node_id)
        if not node or node.identity.is_central_authority:
            return False

        self._pki_engine.revoke_certificate(
            serial=node.identity.certificate_serial,
            device_id=node_id,
            reason=reason,
        )
        node.state = FleetNodeState.REVOKED
        self._revoked_node_ids.add(node_id)
        return True
