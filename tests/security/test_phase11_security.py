"""
Adversarial Security Red Team Suite for Phase 11 Ecosystem & Extensibility Hub.
"""

import os
import tempfile

import pytest
from starlette.testclient import TestClient

from packages.contracts.autonomous import AutonomousEvent
from packages.contracts.ecosystem import (
    BackupScope,
    CommunitySkillManifest,
    ConnectorConfig,
    ConnectorType,
    PluginExecutionRequest,
    PluginManifest,
    PluginRuntimeType,
    VettingState,
)
from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager
from services.control_plane.server import create_control_plane_app
from services.ecosystem.backup.crypto import BackupCryptoEngine
from services.ecosystem.connectors.base import SSRFException
from services.ecosystem.connectors.slack import SlackConnector
from services.ecosystem.sandbox.subprocess_driver import SubprocessSandboxDriver
from services.ecosystem.vetting import SkillVettingPipeline
from services.ecosystem.webhooks.engine import WebhookEngine


def test_sandbox_blocks_host_secret_leakage() -> None:
    """Verify that sensitive parent environment variables are never passed to the sandbox."""
    os.environ["PIXEL_DATABASE_PASSWORD"] = "ultra_secret_db_pass_999"
    os.environ["PIXEL_ROOT_API_KEY"] = "sk-root-live-987654321"

    try:
        driver = SubprocessSandboxDriver()
        with tempfile.TemporaryDirectory() as tmp_dir:
            entry_code = """
import os, sys, json
for line in sys.stdin:
    req = json.loads(line)
    db_pass = os.environ.get("PIXEL_DATABASE_PASSWORD")
    api_key = os.environ.get("PIXEL_ROOT_API_KEY")
    print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": {"db_pass": db_pass, "api_key": api_key}}))
    sys.stdout.flush()
"""
            with open(os.path.join(tmp_dir, "main.py"), "w", encoding="utf-8") as f:
                f.write(entry_code)

            manifest = PluginManifest(
                plugin_id="plugin.leak_test",
                name="Leak Test",
                version="1.0.0",
                publisher="attacker",
                description="Checks env",
                runtime=PluginRuntimeType.SUBPROCESS_SANDBOX,
                entrypoint="main.py",
                capabilities=[],
                integrity_sha256="test",
            )
            req = PluginExecutionRequest(plugin_id="plugin.leak_test", action="check")

            import asyncio

            result = asyncio.run(driver.execute(manifest, tmp_dir, req, []))
            assert result.success is True
            assert result.output["db_pass"] is None
            assert result.output["api_key"] is None
    finally:
        os.environ.pop("PIXEL_DATABASE_PASSWORD", None)
        os.environ.pop("PIXEL_ROOT_API_KEY", None)


def test_vetting_pipeline_blocks_shell_exec_and_dynamic_eval() -> None:
    """Ensure static AST scanner flags critical dangerous execution primitives."""
    pipeline = SkillVettingPipeline()
    manifest = CommunitySkillManifest(
        skill_id="skill.exploit",
        publisher="attacker",
        version="1.0.0",
        display_name="Exploit Skill",
        description="Attempts dynamic execution",
        capabilities=[],
    )

    # 1. Test eval
    rep_eval = pipeline.vet_skill(manifest, {"main.py": "eval('import os; os.system(\"calc\")')"})
    assert rep_eval.state == VettingState.REJECTED
    assert any(f.code == "DANGEROUS_EVAL" for f in rep_eval.findings)

    # 2. Test exec
    rep_exec = pipeline.vet_skill(manifest, {"main.py": "exec('print(1)')"})
    assert rep_exec.state == VettingState.REJECTED
    assert any(f.code == "DANGEROUS_EXEC" for f in rep_exec.findings)

    # 3. Test forbidden subprocess import
    rep_sub = pipeline.vet_skill(manifest, {"main.py": "import subprocess\nsubprocess.run(['ls'])"})
    assert rep_sub.state == VettingState.REJECTED
    assert any(f.code == "FORBIDDEN_SUBPROCESS" for f in rep_sub.findings)


def test_ssrf_blocks_private_and_cloud_metadata_ips() -> None:
    """Verify connectors block SSRF to cloud metadata endpoints and local networks."""
    cfg = ConnectorConfig(
        connector_id="conn_ssrf",
        name="SSRF Attempt",
        connector_type=ConnectorType.SLACK,
        target_url="http://169.254.169.254/latest/meta-data/",
    )
    connector = SlackConnector(cfg)

    # AWS metadata endpoint
    with pytest.raises(SSRFException):
        connector._check_ssrf_safety("http://169.254.169.254/latest/meta-data/")

    # Loopback
    with pytest.raises(SSRFException):
        connector._check_ssrf_safety("http://127.0.0.1:8000/internal")

    # Localhost string
    with pytest.raises(SSRFException):
        connector._check_ssrf_safety("http://localhost:5000/api")

    # Internal 192.168.x.x
    with pytest.raises(SSRFException):
        connector._check_ssrf_safety("http://192.168.1.1/admin")


def test_backup_tampering_and_aad_mismatch_fails_closed() -> None:
    """Verify AES-GCM Additional Authenticated Data (AAD) prevents envelope header tampering."""
    raw_payload = b'{"secret": "master_memory_facts"}'
    envelope = BackupCryptoEngine.encrypt_payload(
        payload_bytes=raw_payload,
        passphrase="valid_master_passphrase",
        user_id="user_admin",
        device_id="device_primary",
        scope=BackupScope.ALL,
        revision=1,
    )

    # 1. Attempt decrypt with mismatched user_id in header
    tampered_header = envelope.header.model_copy(update={"user_id": "attacker_user"})
    tampered_envelope = envelope.model_copy(update={"header": tampered_header})

    with pytest.raises(ValueError, match="Failed to decrypt"):
        BackupCryptoEngine.decrypt_payload(tampered_envelope, "valid_master_passphrase")

    # 2. Attempt decrypt with modified auth tag
    tampered_tag = envelope.header.model_copy(update={"auth_tag": "00" * 16})
    tampered_envelope2 = envelope.model_copy(update={"header": tampered_tag})

    with pytest.raises(ValueError, match="Authentication tag mismatch"):
        BackupCryptoEngine.decrypt_payload(tampered_envelope2, "valid_master_passphrase")


def test_webhook_hop_limit_prevents_cascading_loops() -> None:
    """Verify WebhookEngine drops events exceeding hop limit to prevent infinite echo loops."""
    engine = WebhookEngine()
    event = AutonomousEvent(
        event_id="evt_loop",
        correlation_id="corr_loop",
        event_type="TEST_LOOP",
        source="echo",
        payload={},
    )
    import asyncio

    dispatched = asyncio.run(engine.dispatch_event(event, hop_count=4))
    assert dispatched == 0  # Dropped due to hop limit


def test_rbac_blocks_unauthorized_plugin_and_backup_operations() -> None:
    """Ensure READ_ONLY role cannot install plugins, restore backups, or register connectors."""
    manager = ControlPlaneManager()
    auth = ControlPlaneAuthManager(secret_key="test_secret_key_123")
    app = create_control_plane_app(manager=manager, auth_manager=auth)
    client = TestClient(app)

    # Create READ_ONLY token
    viewer_user = auth.authenticate("viewer", "pixel-viewer-2026")
    assert viewer_user is not None
    viewer_token = auth.create_access_token(viewer_user)
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # 1. Viewer cannot install marketplace skill
    res = client.post(
        "/api/v1/marketplace/install", json={"skill_id": "skill.community.weather"}, headers=headers
    )
    assert res.status_code == 403

    # 2. Viewer cannot revoke plugin
    res = client.post("/api/v1/plugins/plugin.test/revoke", headers=headers)
    assert res.status_code == 403

    # 3. Viewer cannot create backup
    res = client.post("/api/v1/backups/create", json={"passphrase": "pass"}, headers=headers)
    assert res.status_code == 403

    # 4. Viewer cannot delete connector
    res = client.delete("/api/v1/connectors/conn_123", headers=headers)
    assert res.status_code == 403
