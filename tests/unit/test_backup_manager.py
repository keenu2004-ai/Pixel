"""
Unit tests for Backup Manager and Zero-Knowledge Storage.
"""

import tempfile
from collections.abc import Generator

import pytest

from packages.contracts.ecosystem import (
    BackupRestoreRequest,
    BackupScope,
)
from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceIdentity,
    DeviceRole,
    DeviceTrustState,
)
from services.ecosystem.backup.manager import BackupManager
from services.ecosystem.backup.storage import ZeroKnowledgeBackupStorage
from services.memory.manager import MemoryManager
from services.memory.stores.sqlite_store import SQLiteMemoryStore
from services.orchestration.registry import DeviceRegistry


@pytest.fixture
def backup_env() -> Generator[tuple[BackupManager, MemoryManager, DeviceRegistry], None, None]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        mem_db = f"{tmp_dir}/mem.db"
        storage_db = f"{tmp_dir}/backups.db"

        mem_store = SQLiteMemoryStore(db_path=mem_db)
        mem_mgr = MemoryManager(store=mem_store)
        dev_reg = DeviceRegistry()
        storage = ZeroKnowledgeBackupStorage(db_path=storage_db)
        manager = BackupManager(
            storage=storage,
            memory_manager=mem_mgr,
            device_registry=dev_reg,
        )
        yield manager, mem_mgr, dev_reg
        storage.close()
        mem_store.close()


@pytest.mark.asyncio
async def test_backup_create_and_restore_cycle(
    backup_env: tuple[BackupManager, MemoryManager, DeviceRegistry],
) -> None:
    manager, mem_mgr, dev_reg = backup_env

    # 1. Populate Memory and Device Registry
    await mem_mgr.store.set_fact(
        key="prefers_temperature",
        value="24C",
        user_id="user_admin",
        category="preference",
        confidence=0.95,
        provenance="voice_command",
    )

    dev = DeviceIdentity(
        device_id="dev_satellite_01",
        device_name="Living Room Satellite",
        device_type=DeviceRole.SATELLITE_MIC_SPEAKER,
        public_key_fingerprint="sha256_mock_fp_001",
        capabilities=[DeviceCapability.MICROPHONE, DeviceCapability.SPEAKER],
        trust_state=DeviceTrustState.TRUSTED,
    )
    with dev_reg._lock:
        dev_reg._devices[dev.device_id] = dev

    # 2. Create Backup
    envelope = await manager.create_backup(
        passphrase="mypassword123",
        user_id="user_admin",
        scope=BackupScope.ALL,
    )
    assert envelope.header.backup_id is not None

    # Verify listing
    backups = manager.list_backups()
    assert len(backups) == 1
    assert backups[0].backup_id == envelope.header.backup_id

    # 3. Wipe current state
    await mem_mgr.forget_topic("prefers_temperature", user_id="user_admin")
    with dev_reg._lock:
        dev_reg._devices.clear()

    assert len(await mem_mgr.store.list_facts(user_id="user_admin")) == 0
    assert len(dev_reg.list_devices()) == 0

    # 4. Restore from Backup
    restore_req = BackupRestoreRequest(
        backup_id=envelope.header.backup_id,
        passphrase="mypassword123",
    )
    res = await manager.restore_backup(restore_req)
    assert res.success is True
    assert res.memory_facts_restored >= 1
    assert res.devices_restored >= 1

    # 5. Verify restored state
    restored_facts = await mem_mgr.store.list_facts(user_id="user_admin")
    assert len(restored_facts) >= 1
    assert restored_facts[0].key == "prefers_temperature"
    assert restored_facts[0].value == "24C"
    assert dev_reg.get_device("dev_satellite_01") is not None
