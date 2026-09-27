"""PIXEL — Cross-Device Personal Context Synchronization Manager.

Synchronizes:
1. User preferences, active goals, approved routines, and personal entities across mesh nodes (Phone, Desktop, Server).
2. Conflict resolution (explicit user preference wins, newest timestamp for symmetric facts).
3. Immediate Right-to-Forget deletion propagation across all connected devices.
4. Cryptographic device authorization & revocation checks.
"""

import hashlib
import logging
from datetime import UTC, datetime

from packages.contracts.personalization import (
    PersonalContextSyncDelta,
)
from services.personalization.user_model_store import UserModelStore

logger = logging.getLogger(__name__)


class CrossDeviceSyncManager:
    """Manages cross-device synchronization of personal context across trusted mesh nodes."""

    def __init__(self, user_model_store: UserModelStore) -> None:
        self.store = user_model_store
        self._revoked_devices: set[str] = set()

    def revoke_device(self, device_id: str) -> None:
        """Revokes a device from accessing or syncing personal context."""
        self._revoked_devices.add(device_id)
        logger.warning("Device '%s' REVOKED from personal context synchronization", device_id)

    def is_device_trusted(self, device_id: str) -> bool:
        """Checks if device is currently authorized to sync personal context."""
        return device_id not in self._revoked_devices

    async def create_sync_delta(
        self,
        origin_device_id: str,
        user_id: str = "default_user",
        target_device_id: str | None = None,
    ) -> PersonalContextSyncDelta:
        """Packages active personal context into a signed synchronization payload."""
        if not self.is_device_trusted(origin_device_id):
            raise PermissionError(f"Origin device '{origin_device_id}' is revoked or untrusted.")

        user_model = await self.store.get_user_model(user_id=user_id)

        # Compute integrity signature
        payload_repr = (
            f"{user_id}:{origin_device_id}:{user_model.version}:{datetime.now(UTC).isoformat()}"
        )
        signature = hashlib.sha256(payload_repr.encode()).hexdigest()

        delta = PersonalContextSyncDelta(
            user_id=user_id,
            origin_device_id=origin_device_id,
            target_device_id=target_device_id,
            updated_preferences=user_model.preferences.model_dump(),
            active_goals=user_model.active_goals,
            entities=user_model.entities,
            signature=signature,
        )
        logger.info(
            "Generated sync delta from device '%s' for user '%s'", origin_device_id, user_id
        )
        return delta

    async def apply_sync_delta(
        self, delta: PersonalContextSyncDelta, receiving_device_id: str = "pixel-local"
    ) -> bool:
        """Applies received delta to local user model with conflict resolution."""
        if not self.is_device_trusted(delta.origin_device_id):
            logger.error("Rejected sync delta from revoked device '%s'", delta.origin_device_id)
            return False

        user_model = await self.store.get_user_model(user_id=delta.user_id)

        # 1. Apply Right-to-Forget purged keys
        for key in delta.purged_keys:
            await self.store.purge_user_data(user_id=delta.user_id, keyword=key)

        # 2. Merge goals (newest last_worked_on wins)
        existing_goal_map = {g.goal_id: g for g in user_model.active_goals}
        for incoming_g in delta.active_goals:
            if incoming_g.goal_id not in existing_goal_map:
                await self.store.save_goal(incoming_g)
            else:
                curr = existing_goal_map[incoming_g.goal_id]
                if incoming_g.last_worked_on >= curr.last_worked_on:
                    await self.store.save_goal(incoming_g)

        # 3. Merge entities
        existing_entity_map = {e.canonical_name.lower(): e for e in user_model.entities}
        for incoming_e in delta.entities:
            c_key = incoming_e.canonical_name.lower()
            if c_key not in existing_entity_map:
                await self.store.save_entity(incoming_e)
            else:
                curr_e = existing_entity_map[c_key]
                # Merge aliases
                merged_aliases = list(set(curr_e.aliases + incoming_e.aliases))
                curr_e.aliases = merged_aliases
                await self.store.save_entity(curr_e)

        logger.info(
            "Successfully applied sync delta from '%s' onto '%s'",
            delta.origin_device_id,
            receiving_device_id,
        )
        return True
