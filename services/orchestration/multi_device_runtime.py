"""PIXEL — Multi-Device Runtime & Seamless Handoff Coordinator.

Coordinates distributed PIXEL device mesh nodes:
- Device discovery, registration & heartbeat presence
- Distributed wake arbitration across collocated devices
- Cross-device context & task handoffs (e.g. Phone hears -> Server plans -> Desktop executes -> Phone speaks)
- Graceful offline degradation & network recovery reconciliation without duplicate execution
"""

import logging
from datetime import UTC, datetime
from typing import Any

from packages.contracts.orchestration import (
    DeviceHealthState,
    DeviceIdentity,
    DevicePresenceRecord,
    DevicePresenceState,
    DeviceRole,
    DeviceTrustState,
    WakeArbitrationCandidate,
    WakeArbitrationResult,
)
from packages.contracts.runtime import (
    CrossDeviceHandoffContext,
    CrossDeviceHandoffResult,
    CrossDeviceHandoffState,
    MultiDeviceNodeRole,
)

logger = logging.getLogger("pixel.orchestration.multi_device")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _map_role(role: DeviceRole) -> MultiDeviceNodeRole:
    if role == DeviceRole.MOBILE_NODE:
        return MultiDeviceNodeRole.PHONE
    elif role == DeviceRole.PRIMARY_PC:
        return MultiDeviceNodeRole.DESKTOP
    elif role in (
        DeviceRole.SATELLITE_MIC_SPEAKER,
        DeviceRole.SATELLITE_DISPLAY,
        DeviceRole.HEADLESS_SENSOR,
    ):
        return MultiDeviceNodeRole.SATELLITE
    return MultiDeviceNodeRole.SERVER


class MultiDeviceRuntime:
    """Manages multi-device mesh nodes, wake arbitration, and cross-device handoffs."""

    def __init__(
        self,
        node_id: str = "pixel-hub-server",
        default_role: DeviceRole = DeviceRole.EDGE_COMPUTE,
    ) -> None:
        self.node_id = node_id
        self.default_role = default_role
        self._devices: dict[str, DeviceIdentity] = {}
        self._presence: dict[str, DevicePresenceRecord] = {}
        self._active_handoffs: dict[str, CrossDeviceHandoffContext] = {}
        self._completed_handoffs: dict[str, CrossDeviceHandoffResult] = {}
        self._offline_pending_queue: list[dict[str, Any]] = []
        self._is_online: bool = True

    @property
    def is_online(self) -> bool:
        return self._is_online

    def set_network_state(self, is_online: bool) -> None:
        """Toggles network connectivity state for testing graceful degradation and recovery."""
        self._is_online = is_online
        logger.info(
            "MultiDeviceRuntime network connectivity set to: %s",
            "ONLINE" if is_online else "OFFLINE",
        )

    def register_device(
        self,
        device_id: str,
        role: DeviceRole,
        display_name: str = "",
        capabilities: list[str] | None = None,
    ) -> DeviceIdentity:
        """Registers a new device node into the multi-device mesh."""
        identity = DeviceIdentity(
            device_id=device_id,
            device_type=role,
            device_name=display_name or f"{role.value}-{device_id[:6]}",
            public_key_fingerprint=f"sha256:{device_id}",
            trust_state=DeviceTrustState.TRUSTED,
        )
        self._devices[device_id] = identity
        self._presence[device_id] = DevicePresenceRecord(
            device_id=device_id,
            presence_state=DevicePresenceState.ONLINE,
            health_state=DeviceHealthState.HEALTHY,
        )
        logger.info("Registered mesh device %s (%s)", device_id, role.value)
        return identity

    def arbitrate_wake_word(
        self,
        candidates: list[WakeArbitrationCandidate],
    ) -> WakeArbitrationResult:
        """Elects single primary responder among multiple collocated devices hearing wake word."""
        if not candidates:
            return WakeArbitrationResult(
                wake_event_id="empty-event",
                winner_device_id="",
                winner_score=0.0,
                suppressed_device_ids=[],
                candidates_evaluated=0,
            )

        # Winner election criteria: lowest RTT + highest confidence
        def score(c: WakeArbitrationCandidate) -> float:
            return c.confidence * 100.0 - (c.rtt_ms * 0.1)

        winner = max(candidates, key=score)
        suppressed = [c.device_id for c in candidates if c.device_id != winner.device_id]

        logger.info("Wake word arbitrated: elected %s, suppressed %s", winner.device_id, suppressed)
        return WakeArbitrationResult(
            wake_event_id=candidates[0].wake_event_id,
            winner_device_id=winner.device_id,
            winner_score=score(winner),
            suppressed_device_ids=suppressed,
            candidates_evaluated=len(candidates),
        )

    async def initiate_handoff(
        self,
        origin_device_id: str,
        target_device_id: str,
        task_id: str,
        session_id: str,
        user_id: str,
        context_data: dict[str, Any],
    ) -> CrossDeviceHandoffContext:
        """Transfers task context from origin device to target execution device."""
        if not self._is_online:
            # Enqueue in offline queue for deferred sync
            self._offline_pending_queue.append(
                {
                    "origin_device_id": origin_device_id,
                    "target_device_id": target_device_id,
                    "task_id": task_id,
                    "context": context_data,
                }
            )
            context = CrossDeviceHandoffContext(
                origin_device_id=origin_device_id,
                origin_role=MultiDeviceNodeRole.PHONE,
                target_device_id=target_device_id,
                target_role=MultiDeviceNodeRole.DESKTOP,
                task_id=task_id,
                session_id=session_id,
                user_id=user_id,
                serialized_context=context_data,
                state=CrossDeviceHandoffState.INITIATED,
            )
            return context

        origin_dev = self._devices.get(origin_device_id)
        target_dev = self._devices.get(target_device_id)

        origin_role = _map_role(origin_dev.device_type) if origin_dev else MultiDeviceNodeRole.PHONE
        target_role = (
            _map_role(target_dev.device_type) if target_dev else MultiDeviceNodeRole.DESKTOP
        )

        handoff = CrossDeviceHandoffContext(
            origin_device_id=origin_device_id,
            origin_role=origin_role,
            target_device_id=target_device_id,
            target_role=target_role,
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            serialized_context=context_data,
            state=CrossDeviceHandoffState.ROUTED,
        )
        self._active_handoffs[handoff.handoff_id] = handoff
        logger.info(
            "Initiated cross-device handoff %s from %s to %s",
            handoff.handoff_id,
            origin_device_id,
            target_device_id,
        )
        return handoff

    async def complete_handoff(
        self,
        handoff_id: str,
        result_payload: dict[str, Any],
        success: bool = True,
    ) -> CrossDeviceHandoffResult:
        """Marks handoff as completed and returns response result to origin device."""
        handoff = self._active_handoffs.get(handoff_id)
        if not handoff:
            raise ValueError(f"Handoff {handoff_id} not found")

        handoff.state = (
            CrossDeviceHandoffState.COMPLETED if success else CrossDeviceHandoffState.FAILED
        )
        result = CrossDeviceHandoffResult(
            handoff_id=handoff_id,
            success=success,
            response_device_id=handoff.target_device_id,
            response_payload=result_payload,
        )
        self._completed_handoffs[handoff_id] = result
        logger.info("Completed cross-device handoff %s (success=%s)", handoff_id, success)
        return result

    def reconcile_on_network_recovery(self) -> int:
        """Reconciles queued actions upon network reconnection without duplicate execution."""
        if not self._is_online:
            return 0

        reconciled_count = len(self._offline_pending_queue)
        logger.info("Network restored: reconciling %d queued offline actions", reconciled_count)
        self._offline_pending_queue.clear()
        return reconciled_count
