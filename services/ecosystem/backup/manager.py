"""
Zero-Knowledge Encrypted Backup Manager for PIXEL.

Coordinates client-side snapshot creation, encryption, synchronization,
and deterministic restoration into MemoryManager and DeviceRegistry.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from packages.contracts.ecosystem import (
    BackupMetadataView,
    BackupRestoreRequest,
    BackupRestoreResult,
    BackupScope,
    EncryptedBackupEnvelope,
)
from packages.contracts.memory import FactRecord
from packages.contracts.orchestration import DeviceIdentity
from services.ecosystem.backup.crypto import BackupCryptoEngine
from services.ecosystem.backup.storage import ZeroKnowledgeBackupStorage
from services.memory.manager import MemoryManager
from services.orchestration.registry import DeviceRegistry

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages Zero-Knowledge encrypted backup creation, sync, and restoration."""

    def __init__(
        self,
        storage: ZeroKnowledgeBackupStorage | None = None,
        memory_manager: MemoryManager | None = None,
        device_registry: DeviceRegistry | None = None,
    ):
        self.storage = storage or ZeroKnowledgeBackupStorage()
        self.memory_manager = memory_manager
        self.device_registry = device_registry

    async def create_backup(
        self,
        passphrase: str,
        user_id: str = "default_user",
        device_id: str = "primary_device",
        scope: BackupScope = BackupScope.ALL,
    ) -> EncryptedBackupEnvelope:
        """Create a client-side encrypted backup snapshot of memory and device configurations."""
        snapshot_data: dict[str, Any] = {
            "version": "1.0.0",
            "scope": scope.value,
            "created_at": time.time(),
            "memory": {},
            "devices": [],
        }

        # 1. Export Memory Tier Data
        if self.memory_manager and scope in [
            BackupScope.ALL,
            BackupScope.MEMORY_ONLY,
            BackupScope.SEMANTIC_ONLY,
            BackupScope.EPISODIC_ONLY,
        ]:
            facts = await self.memory_manager.store.list_facts(user_id=user_id)
            snapshot_data["memory"]["facts"] = [f.model_dump() for f in facts]

        # 2. Export Device Registry Data
        if self.device_registry and scope in [BackupScope.ALL, BackupScope.DEVICE_CONFIG_ONLY]:
            devices = self.device_registry.list_devices()
            snapshot_data["devices"] = [d.model_dump() for d in devices]

        # 3. Serialize and Encrypt Client-Side
        payload_bytes = json.dumps(snapshot_data, default=str).encode("utf-8")
        envelope = BackupCryptoEngine.encrypt_payload(
            payload_bytes=payload_bytes,
            passphrase=passphrase,
            user_id=user_id,
            device_id=device_id,
            scope=scope,
        )

        # 4. Store Envelope
        self.storage.store_envelope(envelope)
        logger.info(
            f"Created encrypted backup envelope {envelope.header.backup_id} (scope: {scope.value})"
        )
        return envelope

    async def restore_backup(
        self,
        request: BackupRestoreRequest,
    ) -> BackupRestoreResult:
        """Decrypt and restore a backup envelope into active runtime stores."""
        start_time = time.perf_counter()
        envelope = self.storage.get_envelope(request.backup_id)
        if not envelope:
            return BackupRestoreResult(
                backup_id=request.backup_id,
                success=False,
                error=f"Backup envelope '{request.backup_id}' not found in storage",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 1. Decrypt and verify integrity
        try:
            decrypted_bytes = BackupCryptoEngine.decrypt_payload(envelope, request.passphrase)
            snapshot_data = json.loads(decrypted_bytes.decode("utf-8"))
        except Exception as ex:
            logger.warning(f"Backup restoration failed for {request.backup_id}: {ex}")
            return BackupRestoreResult(
                backup_id=request.backup_id,
                success=False,
                error=f"Decryption failed: {str(ex)}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        facts_restored = 0
        devices_restored = 0

        # 2. Restore Memory Facts
        if self.memory_manager and "memory" in snapshot_data and "facts" in snapshot_data["memory"]:
            for f_dict in snapshot_data["memory"]["facts"]:
                try:
                    fact = FactRecord.model_validate(f_dict)
                    await self.memory_manager.store.set_fact(
                        key=fact.key,
                        value=fact.value,
                        user_id=fact.user_id,
                        category=fact.category,
                        provenance=fact.provenance,
                        confidence=fact.confidence,
                    )
                    facts_restored += 1
                except Exception as ferr:
                    logger.debug(f"Skipping malformed fact during restore: {ferr}")

        # 3. Restore Device Topology
        if self.device_registry and "devices" in snapshot_data:
            with self.device_registry._lock:
                for d_dict in snapshot_data["devices"]:
                    try:
                        dev = DeviceIdentity.model_validate(d_dict)
                        self.device_registry._devices[dev.device_id] = dev
                        devices_restored += 1
                    except Exception as derr:
                        logger.debug(f"Skipping malformed device during restore: {derr}")

        duration = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Successfully restored backup {request.backup_id}: {facts_restored} facts, {devices_restored} devices in {duration:.2f}ms"
        )
        return BackupRestoreResult(
            backup_id=request.backup_id,
            success=True,
            restored_items_count=facts_restored + devices_restored,
            memory_facts_restored=facts_restored,
            devices_restored=devices_restored,
            duration_ms=duration,
        )

    def list_backups(self, user_id: str | None = None) -> list[BackupMetadataView]:
        """List safe metadata for all available backups."""
        return self.storage.list_envelopes(user_id=user_id)

    def delete_backup(self, backup_id: str) -> bool:
        """Delete an encrypted backup envelope."""
        return self.storage.delete_envelope(backup_id)
