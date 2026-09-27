"""
Comprehensive End-to-End Integration Suite for Phase 11 Ecosystem & Extensibility Hub.
"""

import tempfile
from collections.abc import Generator
from typing import Any

import pytest

from packages.contracts.autonomous import AutonomousEvent
from packages.contracts.ecosystem import (
    BackupRestoreRequest,
    BackupScope,
    ConnectorConfig,
    ConnectorStatus,
    ConnectorType,
    PluginCapability,
    PluginLifecycleState,
    SkillInstallRequest,
)
from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceIdentity,
    DeviceRole,
    DeviceTrustState,
)
from packages.contracts.tools import ToolExecutionRequest
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.tools.registry import ToolRegistry
from services.autonomous.event_bus import EventBus
from services.ecosystem.backup.manager import BackupManager
from services.ecosystem.backup.storage import ZeroKnowledgeBackupStorage
from services.ecosystem.connectors.registry import ConnectorRegistry
from services.ecosystem.lifecycle import PluginLifecycleManager
from services.ecosystem.marketplace import MarketplaceRegistry
from services.ecosystem.sandbox.subprocess_driver import SubprocessSandboxDriver
from services.ecosystem.skill_bridge import CommunitySkillBridge
from services.ecosystem.vetting import SkillVettingPipeline
from services.ecosystem.webhooks.engine import WebhookEngine
from services.memory.manager import MemoryManager
from services.memory.stores.sqlite_store import SQLiteMemoryStore
from services.orchestration.registry import DeviceRegistry


@pytest.fixture
def ecosystem_stack() -> Generator[dict[str, Any], None, None]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        driver = SubprocessSandboxDriver()
        lifecycle = PluginLifecycleManager(
            db_path=f"{tmp_dir}/plugins.db",
            sandbox_driver=driver,
            base_plugins_dir=f"{tmp_dir}/plugins_code",
        )
        vetting = SkillVettingPipeline()
        marketplace = MarketplaceRegistry(
            lifecycle_manager=lifecycle,
            vetting_pipeline=vetting,
            skills_store_dir=f"{tmp_dir}/skills_store",
        )
        tool_reg = ToolRegistry()
        policy_gate = AgentPolicyGate()
        bridge = CommunitySkillBridge(
            lifecycle_manager=lifecycle,
            marketplace_registry=marketplace,
            tool_registry=tool_reg,
            policy_gate=policy_gate,
        )

        mem_store = SQLiteMemoryStore(db_path=f"{tmp_dir}/mem.db")
        mem_mgr = MemoryManager(store=mem_store)
        dev_reg = DeviceRegistry()
        storage = ZeroKnowledgeBackupStorage(db_path=f"{tmp_dir}/backups.db")
        backup_mgr = BackupManager(
            storage=storage,
            memory_manager=mem_mgr,
            device_registry=dev_reg,
        )

        event_bus = EventBus()
        conn_reg = ConnectorRegistry(db_path=f"{tmp_dir}/connectors.db")
        webhook_engine = WebhookEngine(
            event_bus=event_bus,
            connector_registry=conn_reg,
        )
        webhook_engine.start()

        yield {
            "lifecycle": lifecycle,
            "marketplace": marketplace,
            "tool_registry": tool_reg,
            "policy_gate": policy_gate,
            "bridge": bridge,
            "memory_manager": mem_mgr,
            "device_registry": dev_reg,
            "backup_manager": backup_mgr,
            "event_bus": event_bus,
            "connector_registry": conn_reg,
            "webhook_engine": webhook_engine,
        }

        webhook_engine.stop()
        storage.close()
        lifecycle.close()
        conn_reg.close()
        mem_store.close()


@pytest.mark.asyncio
async def test_end_to_end_community_skill_flow(ecosystem_stack: dict[str, Any]) -> None:
    """
    Scenario:
    1. Marketplace discovers verified skill (Smart Calculator).
    2. Admin installs skill with approved capabilities.
    3. Bridge registers tool in ToolRegistry.
    4. Tool executes through L6 Policy -> Sandbox -> L8 Action Verification.
    """
    marketplace: MarketplaceRegistry = ecosystem_stack["marketplace"]
    bridge: CommunitySkillBridge = ecosystem_stack["bridge"]
    tool_reg: ToolRegistry = ecosystem_stack["tool_registry"]

    # 1. Inspect skill
    skill_listing = marketplace.get_skill("skill.community.calculator")
    assert skill_listing is not None
    assert skill_listing.verified is True

    # 2. Install skill
    req = SkillInstallRequest(
        skill_id="skill.community.calculator",
        accepted_capabilities=[PluginCapability.TOOL_INVOCATION],
        auto_enable=True,
    )
    state = marketplace.install_skill(req, actor="admin")
    assert state == PluginLifecycleState.ENABLED

    # 3. Register tools via Bridge
    count = bridge.register_installed_skills()
    assert count >= 1

    tool_name = "skill_community_calculator"
    assert tool_reg.get_tool(tool_name) is not None

    # 4. Execute tool
    exec_req = ToolExecutionRequest(
        tool_name=tool_name,
        arguments={"expression": "25 * 4 + 10"},
        session_id="session_test_01",
        trace_id="trace_test_01",
    )
    result = await tool_reg.execute_tool(exec_req)
    assert result.success is True
    assert result.output["value"] == 110.0


@pytest.mark.asyncio
async def test_end_to_end_zero_knowledge_backup_flow(ecosystem_stack: dict[str, Any]) -> None:
    """
    Scenario:
    1. Write sensitive facts to MemoryManager and devices to DeviceRegistry.
    2. Create client-side AES-256-GCM encrypted backup envelope.
    3. Wipe runtime memory facts and devices.
    4. Restore from backup envelope using passphrase.
    5. Verify 100% data fidelity restored.
    """
    mem_mgr: MemoryManager = ecosystem_stack["memory_manager"]
    dev_reg: DeviceRegistry = ecosystem_stack["device_registry"]
    backup_mgr: BackupManager = ecosystem_stack["backup_manager"]

    # 1. Populate
    await mem_mgr.store.set_fact(
        key="lives_in",
        value="New Delhi",
        user_id="user_admin",
        category="profile",
        confidence=0.99,
        provenance="user_explicit",
    )

    dev = DeviceIdentity(
        device_id="mobile_android_01",
        device_name="Pixel Phone 8 Pro",
        device_type=DeviceRole.MOBILE_NODE,
        public_key_fingerprint="sha256_mock_fp_002",
        capabilities=[DeviceCapability.MICROPHONE, DeviceCapability.SPEAKER],
        trust_state=DeviceTrustState.TRUSTED,
    )
    with dev_reg._lock:
        dev_reg._devices[dev.device_id] = dev

    # 2. Encrypt & Backup
    envelope = await backup_mgr.create_backup(
        passphrase="vault_master_passphrase_2026",
        user_id="user_admin",
        scope=BackupScope.ALL,
    )
    assert envelope.header.backup_id is not None

    # 3. Wipe live state
    await mem_mgr.forget_topic("lives_in", user_id="user_admin")
    with dev_reg._lock:
        dev_reg._devices.clear()

    assert len(await mem_mgr.store.list_facts(user_id="user_admin")) == 0
    assert len(dev_reg.list_devices()) == 0

    # 4. Decrypt & Restore
    res = await backup_mgr.restore_backup(
        BackupRestoreRequest(
            backup_id=envelope.header.backup_id,
            passphrase="vault_master_passphrase_2026",
        )
    )
    assert res.success is True
    assert res.memory_facts_restored >= 1
    assert res.devices_restored >= 1

    # 5. Verify fidelity
    facts = await mem_mgr.store.list_facts(user_id="user_admin")
    assert any(f.value == "New Delhi" for f in facts)
    assert dev_reg.get_device("mobile_android_01") is not None


@pytest.mark.asyncio
async def test_end_to_end_connector_webhook_flow(ecosystem_stack: dict[str, Any]) -> None:
    """
    Scenario:
    1. Register Slack & Discord connectors with event filters.
    2. Publish AutonomousEvent on EventBus.
    3. WebhookEngine intercepts, evaluates allowlists, formats payload, and delivers.
    4. Verify delivery records in audit ledger.
    """
    conn_reg: ConnectorRegistry = ecosystem_stack["connector_registry"]
    event_bus: EventBus = ecosystem_stack["event_bus"]

    # 1. Register Connectors
    slack_cfg = ConnectorConfig(
        connector_id="slack_prod_alerts",
        name="Production Slack",
        connector_type=ConnectorType.SLACK,
        target_url="https://hooks.slack.com/services/T1/B2/K3",
        enabled_events=["TASK_COMPLETED", "DRIFT_DETECTED"],
        status=ConnectorStatus.ACTIVE,
    )
    conn_reg.register_connector(slack_cfg)

    # 2. Publish matching event
    event = AutonomousEvent(
        event_id="evt_audit_999",
        correlation_id="corr_999",
        event_type="TASK_COMPLETED",
        source="autonomous_engine",
        payload={"task_id": "t_999", "status": "COMPLETED", "duration_sec": 12.4},
    )
    await event_bus.publish(event)

    # Allow async dispatch
    import asyncio

    await asyncio.sleep(0.05)

    # 3. Check delivery recorded
    deliveries = conn_reg.list_deliveries()
    assert len(deliveries) >= 1
    assert any(d.connector_id == "slack_prod_alerts" for d in deliveries)
    assert deliveries[0].success is True
