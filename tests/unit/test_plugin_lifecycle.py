"""
Unit tests for Plugin Lifecycle Manager and Revocation Ledger.
"""

import os
import tempfile
from collections.abc import Generator

import pytest

from packages.contracts.ecosystem import (
    PluginCapability,
    PluginExecutionRequest,
    PluginLifecycleState,
    PluginManifest,
    PluginRiskClass,
    PluginRuntimeType,
)
from services.ecosystem.lifecycle import PluginLifecycleManager
from services.ecosystem.sandbox.subprocess_driver import SubprocessSandboxDriver


@pytest.fixture
def lifecycle_mgr() -> Generator[PluginLifecycleManager, None, None]:
    with tempfile.TemporaryDirectory() as base_dir:
        driver = SubprocessSandboxDriver()
        mgr = PluginLifecycleManager(
            db_path=":memory:",
            sandbox_driver=driver,
            base_plugins_dir=base_dir,
        )
        yield mgr
        mgr.close()


@pytest.mark.asyncio
async def test_plugin_lifecycle_state_flow(lifecycle_mgr: PluginLifecycleManager) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        entry_code = """
import sys, json
for line in sys.stdin:
    req = json.loads(line)
    print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": "pong"}))
    sys.stdout.flush()
"""
        with open(os.path.join(tmp_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write(entry_code)

        manifest = PluginManifest(
            plugin_id="plugin.ping",
            name="Ping Service",
            version="1.0.0",
            publisher="test_org",
            description="Returns pong",
            runtime=PluginRuntimeType.SUBPROCESS_SANDBOX,
            entrypoint="main.py",
            capabilities=[PluginCapability.NETWORK_OUTBOUND],
            risk_class=PluginRiskClass.LOW,
            integrity_sha256="test",
        )

        # 1. Register discovered
        state = lifecycle_mgr.register_discovered_plugin(manifest, tmp_dir)
        assert state == PluginLifecycleState.DISCOVERED

        # 2. Cannot execute while in DISCOVERED
        req = PluginExecutionRequest(plugin_id="plugin.ping", action="ping")
        res = await lifecycle_mgr.execute_plugin_action(req)
        assert res.success is False
        assert res.error is not None and "not in ENABLED state" in res.error

        # 3. Approve and install
        state = lifecycle_mgr.approve_and_install(
            plugin_id="plugin.ping",
            granted_capabilities=[PluginCapability.NETWORK_OUTBOUND],
            auto_enable=True,
        )
        assert state == PluginLifecycleState.ENABLED

        # 4. Now execute successfully
        res = await lifecycle_mgr.execute_plugin_action(req)
        assert res.success is True
        assert res.output == "pong"

        # 5. Disable plugin
        state = lifecycle_mgr.disable_plugin("plugin.ping")
        assert state == PluginLifecycleState.DISABLED
        res = await lifecycle_mgr.execute_plugin_action(req)
        assert res.success is False

        # 6. Re-enable plugin
        state = lifecycle_mgr.enable_plugin("plugin.ping")
        assert state == PluginLifecycleState.ENABLED

        # 7. Emergency Revoke
        await lifecycle_mgr.emergency_revoke("plugin.ping", "Security vulnerability detected")
        assert lifecycle_mgr.is_revoked("plugin.ping") is True

        # 8. Execution fails after revocation
        res = await lifecycle_mgr.execute_plugin_action(req)
        assert res.success is False
        assert res.error is not None and "permanently REVOKED" in res.error


def test_plugin_permission_expansion_detection(lifecycle_mgr: PluginLifecycleManager) -> None:
    with tempfile.TemporaryDirectory() as dir1, tempfile.TemporaryDirectory() as dir2:
        m1 = PluginManifest(
            plugin_id="plugin.smart",
            name="Smart Tool",
            version="1.0.0",
            publisher="test",
            description="v1",
            runtime=PluginRuntimeType.SUBPROCESS_SANDBOX,
            entrypoint="main.py",
            capabilities=[PluginCapability.READ_CONVERSATION],
            risk_class=PluginRiskClass.LOW,
            integrity_sha256="hash1",
        )
        lifecycle_mgr.register_discovered_plugin(m1, dir1)
        lifecycle_mgr.approve_and_install(
            plugin_id="plugin.smart",
            granted_capabilities=[PluginCapability.READ_CONVERSATION],
            auto_enable=True,
        )

        # Update v2 with expanded capability (NETWORK_OUTBOUND)
        m2 = PluginManifest(
            plugin_id="plugin.smart",
            name="Smart Tool",
            version="2.0.0",
            publisher="test",
            description="v2 with network",
            runtime=PluginRuntimeType.SUBPROCESS_SANDBOX,
            entrypoint="main.py",
            capabilities=[PluginCapability.READ_CONVERSATION, PluginCapability.NETWORK_OUTBOUND],
            risk_class=PluginRiskClass.MEDIUM,
            integrity_sha256="hash2",
        )

        next_state, expanded = lifecycle_mgr.update_plugin(
            plugin_id="plugin.smart",
            new_manifest=m2,
            new_code_dir=dir2,
        )

        # Must detect expansion and transition to INSTALLED (pending re-approval)
        assert PluginCapability.NETWORK_OUTBOUND in expanded
        assert next_state == PluginLifecycleState.INSTALLED
