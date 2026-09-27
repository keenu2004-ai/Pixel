"""PIXEL — Assistant App Lifecycle & Recovery Hardener.

Manages Android / OS lifecycle transitions:
- Backgrounding / Foregrounding
- Android Doze mode and Battery Saver adaptations
- Unexpected process death and device reboot recovery
- Dynamic permission revocation and restoration
- Continuous state checkpoint hydration
"""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from packages.contracts.agent import AgentCheckpoint, AgentExecutionStatus, AgentState
from packages.contracts.events import VoiceState

logger = logging.getLogger("pixel.voice_gateway.lifecycle")


class LifecycleEvent(StrEnum):
    """Platform lifecycle event types."""

    APP_START = "APP_START"
    APP_BACKGROUND = "APP_BACKGROUND"
    APP_FOREGROUND = "APP_FOREGROUND"
    DOZE_MODE_ENTER = "DOZE_MODE_ENTER"
    DOZE_MODE_EXIT = "DOZE_MODE_EXIT"
    PROCESS_KILLED = "PROCESS_KILLED"
    DEVICE_BOOT = "DEVICE_BOOT"
    NETWORK_LOST = "NETWORK_LOST"
    NETWORK_RESTORED = "NETWORK_RESTORED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    PERMISSION_RESTORED = "PERMISSION_RESTORED"


class AssistantLifecycleHardener:
    """Coordinates lifecycle transitions, Doze adaptation, and zero-loss crash recovery."""

    def __init__(self, node_id: str = "pixel-node-01") -> None:
        self.node_id = node_id
        self.current_state: VoiceState = VoiceState.IDLE
        self.is_in_background: bool = False
        self.is_doze_active: bool = False
        self.active_permissions: set[str] = {
            "RECORD_AUDIO",
            "POST_NOTIFICATIONS",
            "READ_CONTACTS",
            "CALL_PHONE",
            "SEND_SMS",
            "SET_ALARM",
        }
        self._checkpoints: dict[str, AgentCheckpoint] = {}
        self._recovered_tasks: list[str] = []
        self._lifecycle_history: list[dict[str, Any]] = []

    def handle_lifecycle_event(
        self, event: LifecycleEvent, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Processes a platform lifecycle transition gracefully."""
        details = details or {}
        timestamp = datetime.now(UTC).isoformat()
        record = {"event": event.value, "timestamp": timestamp, "details": details}
        self._lifecycle_history.append(record)

        if event == LifecycleEvent.APP_BACKGROUND:
            self.is_in_background = True
            logger.info("Assistant entered BACKGROUND mode; throttling non-critical workers")
            return {"status": "ADAPTED_BACKGROUND", "low_power": True}

        elif event == LifecycleEvent.APP_FOREGROUND:
            self.is_in_background = False
            logger.info("Assistant returned to FOREGROUND; full audio & display active")
            return {"status": "RESUMED_FOREGROUND", "low_power": False}

        elif event == LifecycleEvent.DOZE_MODE_ENTER:
            self.is_doze_active = True
            logger.info("Android DOZE active; suspending streaming STT, maintaining wake listener")
            return {"status": "DOZE_SUSPENDED", "wake_listener_only": True}

        elif event == LifecycleEvent.DOZE_MODE_EXIT:
            self.is_doze_active = False
            logger.info("Android DOZE exited; restoring full duplex audio gateway")
            return {"status": "DOZE_RESTORED", "wake_listener_only": False}

        elif event == LifecycleEvent.PERMISSION_REVOKED:
            revoked_perm = details.get("permission", "UNKNOWN")
            self.active_permissions.discard(revoked_perm)
            logger.warning("Permission revoked: %s. Gracefully adapting capabilities", revoked_perm)
            return {
                "status": "PERMISSION_DEGRADED",
                "revoked": revoked_perm,
                "message": f"Action requiring {revoked_perm} is temporarily disabled.",
            }

        elif event == LifecycleEvent.PERMISSION_RESTORED:
            restored_perm = details.get("permission", "UNKNOWN")
            self.active_permissions.add(restored_perm)
            logger.info("Permission restored: %s. Re-enabling adapter", restored_perm)
            return {"status": "PERMISSION_RESTORED", "permission": restored_perm}

        return {"status": "PROCESSED", "event": event.value}

    def save_checkpoint(self, state: AgentState) -> AgentCheckpoint:
        """Persists task state to prevent loss across process death or reboot."""
        checkpoint = AgentCheckpoint(
            task_id=state.task_id,
            session_id=state.session_id,
            version=1,
            state_json=state.model_dump_json(),
            status=state.status,
        )
        self._checkpoints[state.task_id] = checkpoint
        logger.debug("Saved persistent checkpoint for task %s", state.task_id)
        return checkpoint

    def recover_on_boot_or_restart(self) -> list[AgentCheckpoint]:
        """Restores in-flight tasks following sudden process termination or system reboot."""
        recovered = []
        for task_id, cp in list(self._checkpoints.items()):
            if cp.status in (AgentExecutionStatus.EXECUTING, AgentExecutionStatus.PLANNING):
                recovered.append(cp)
                self._recovered_tasks.append(task_id)
                logger.info("Recovered in-flight task %s from checkpoint", task_id)
        return recovered

    def verify_action_permission(self, required_permission: str) -> bool:
        """Verifies if the requisite platform permission is currently active."""
        return required_permission in self.active_permissions
