"""Cross-Device Context & Task Handoff Manager.

Handles safe, scoped conversation context replication, optimistic concurrency
leasing for task migration, BaseCheckpointer state alignment, and L6 approval
token security validation.
"""

import secrets
import threading
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from packages.contracts.orchestration import (
    ContextHandoffPayload,
    DeviceCapability,
    DevicePresenceState,
    DeviceTrustState,
    TaskHandoffPayload,
)
from services.orchestration.registry import DeviceRegistry, PresenceManager

_SENSITIVE_KEY_PATTERNS = {
    "auth_token",
    "token",
    "api_key",
    "secret",
    "password",
    "private_key",
    "credential",
    "access_key",
}


def _sanitize_context(raw_dict: dict[str, Any]) -> dict[str, Any]:
    """Recursively strip sensitive keys and secret credentials from context."""
    sanitized: dict[str, Any] = {}
    for key, value in raw_dict.items():
        if any(pat in key.lower() for pat in _SENSITIVE_KEY_PATTERNS):
            continue
        if isinstance(value, dict):
            sanitized[key] = _sanitize_context(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _sanitize_context(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


class HandoffManager:
    """Orchestrates secure session and task migration across PIXEL devices."""

    def __init__(
        self,
        registry: DeviceRegistry,
        presence: PresenceManager,
    ) -> None:
        self.registry = registry
        self.presence = presence
        self._active_leases: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def initiate_context_handoff(
        self,
        source_device_id: str,
        target_device_id: str,
        session_id: str,
        conversation_context: dict[str, Any],
        active_language: str = "en",
    ) -> ContextHandoffPayload:
        """Transfer scoped dialog context between trusted online devices."""
        with self._lock:
            # Validate source device
            source = self.registry.get_device(source_device_id)
            if not source or source.trust_state != DeviceTrustState.TRUSTED:
                raise PermissionError(f"Source device {source_device_id} is not trusted.")

            # Validate target device
            target = self.registry.get_device(target_device_id)
            if not target or target.trust_state != DeviceTrustState.TRUSTED:
                raise PermissionError(f"Target device {target_device_id} is not trusted.")

            # Validate target presence
            presence = self.presence.get_presence(target_device_id)
            if not presence or presence.presence_state != DevicePresenceState.ONLINE:
                raise RuntimeError(f"Target device {target_device_id} is not currently online.")

            # Sanitize context
            clean_context = _sanitize_context(conversation_context)

            return ContextHandoffPayload(
                handoff_id=uuid4().hex,
                source_device_id=source_device_id,
                target_device_id=target_device_id,
                session_id=session_id,
                conversation_context=clean_context,
                active_language=active_language,
                timestamp=datetime.now(UTC),
            )

    def initiate_task_handoff(
        self,
        source_device_id: str,
        target_device_id: str,
        task_id: str,
        current_version: int,
        plan_steps: list[dict[str, Any]],
        current_step_index: int = 0,
        pending_approval: dict[str, Any] | None = None,
        state_snapshot: dict[str, Any] | None = None,
        required_capability: DeviceCapability | None = None,
    ) -> TaskHandoffPayload:
        """Issue an optimistic concurrency lease and migrate task execution to target node."""
        with self._lock:
            # Validate source & target trust
            source = self.registry.get_device(source_device_id)
            if not source or source.trust_state != DeviceTrustState.TRUSTED:
                raise PermissionError(f"Source device {source_device_id} is not trusted.")

            target = self.registry.get_device(target_device_id)
            if not target or target.trust_state != DeviceTrustState.TRUSTED:
                raise PermissionError(f"Target device {target_device_id} is not trusted.")

            # Check target capabilities if task requires specific hardware (e.g. DESKTOP_CONTROL)
            if required_capability and required_capability not in target.capabilities:
                raise ValueError(
                    f"Target device {target_device_id} lacks required capability: {required_capability.value}"
                )

            # Check target presence
            presence = self.presence.get_presence(target_device_id)
            if not presence or presence.presence_state != DevicePresenceState.ONLINE:
                raise RuntimeError(f"Target device {target_device_id} is not currently online.")

            # Check existing lease for task
            existing_lease = self._active_leases.get(task_id)
            if existing_lease and existing_lease["version"] >= current_version + 1:
                raise RuntimeError(f"Stale task handoff attempt for task {task_id}: newer lease version exists.")

            new_version = current_version + 1
            lease_token = secrets.token_hex(24)

            self._active_leases[task_id] = {
                "lease_token": lease_token,
                "version": new_version,
                "owner_device_id": target_device_id,
                "issued_at": datetime.now(UTC),
            }

            clean_snapshot = _sanitize_context(state_snapshot or {})

            return TaskHandoffPayload(
                handoff_id=uuid4().hex,
                task_id=task_id,
                source_device_id=source_device_id,
                target_device_id=target_device_id,
                task_version=new_version,
                concurrency_lease_token=lease_token,
                plan_steps=plan_steps,
                current_step_index=current_step_index,
                pending_approval=pending_approval,
                state_snapshot=clean_snapshot,
                timestamp=datetime.now(UTC),
            )

    def complete_task_handoff(
        self,
        task_id: str,
        target_device_id: str,
        lease_token: str,
    ) -> bool:
        """Validate optimistic lease token on target node to confirm task ownership."""
        with self._lock:
            lease = self._active_leases.get(task_id)
            if not lease:
                return False

            if lease["owner_device_id"] != target_device_id:
                return False

            if not secrets.compare_digest(lease["lease_token"], lease_token):
                return False

            return True

    def get_task_lease(self, task_id: str) -> dict[str, Any] | None:
        """Get active concurrency lease info for a task."""
        with self._lock:
            return self._active_leases.get(task_id)
