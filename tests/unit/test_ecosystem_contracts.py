"""
Unit tests for Phase 11 Ecosystem & Extensibility Contracts.
"""

import pytest
from pydantic import ValidationError

from packages.contracts.ecosystem import (
    BackupHeader,
    BackupScope,
    CommunitySkillManifest,
    ConnectorConfig,
    ConnectorStatus,
    ConnectorType,
    EncryptedBackupEnvelope,
    FindingSeverity,
    PluginCapability,
    PluginManifest,
    PluginRiskClass,
    PluginRuntimeType,
    SecurityFinding,
    SkillVettingReport,
    VettingState,
    WebhookDeliveryRecord,
)


def test_plugin_manifest_validation() -> None:
    manifest = PluginManifest(
        plugin_id="plugin.weather",
        name="Live Weather",
        version="1.0.0",
        publisher="community.weather_org",
        description="Fetches live weather reports.",
        runtime=PluginRuntimeType.SUBPROCESS_SANDBOX,
        entrypoint="main.py",
        capabilities=[PluginCapability.NETWORK_OUTBOUND],
        risk_class=PluginRiskClass.LOW,
        dependencies=["httpx"],
        config_schema={"api_key": {"type": "string"}},
        integrity_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert manifest.plugin_id == "plugin.weather"
    assert manifest.capabilities == [PluginCapability.NETWORK_OUTBOUND]
    assert manifest.risk_class == PluginRiskClass.LOW


def test_plugin_manifest_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(
            {
                "plugin_id": "plugin.bad",
                "name": "Bad Plugin",
                "version": "1.0.0",
                "publisher": "attacker",
                "description": "Exploit",
                "entrypoint": "main.py",
                "integrity_sha256": "abc",
                "malicious_arbitrary_field": "payload",  # Extra field forbidden
            }
        )


def test_community_skill_and_vetting_report() -> None:
    finding = SecurityFinding(
        code="DANGEROUS_IMPORT",
        severity=FindingSeverity.HIGH,
        message="Use of forbidden os.system call",
        file="plugin.py",
        line=42,
        rule_id="RULE_NO_SHELL_EXEC",
    )
    report = SkillVettingReport(
        manifest_id="skill.calc",
        state=VettingState.REJECTED,
        findings=[finding],
        scanner_version="1.0.0",
        passed=False,
    )
    skill = CommunitySkillManifest(
        skill_id="skill.calc",
        publisher="pixel.community",
        version="1.0.0",
        display_name="Smart Calculator",
        description="Math parsing tool",
        triggers=["calculate", "math"],
        input_schema={"expression": {"type": "string"}},
        output_schema={"result": {"type": "number"}},
        capabilities=[PluginCapability.TOOL_INVOCATION],
        vetting_report=report,
    )
    assert skill.vetting_report is not None
    assert skill.vetting_report.state == VettingState.REJECTED
    assert len(skill.vetting_report.findings) == 1
    assert skill.vetting_report.findings[0].severity == FindingSeverity.HIGH


def test_encrypted_backup_envelope() -> None:
    header = BackupHeader(
        backup_id="bk_001",
        user_id="user_admin",
        device_id="dev_pc_01",
        revision=1,
        scope=BackupScope.ALL,
        kdf_salt="a1b2c3d4e5f60718293a4b5c6d7e8f90",
        kdf_iterations=100_000,
        nonce="123456789012345678901234",
        auth_tag="abcdefabcdefabcdefabcdefabcdefab",
        ciphertext_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    envelope = EncryptedBackupEnvelope(
        header=header,
        ciphertext_b64="SGVsbG8gV29ybGQgRW5jcnlwdGVkIFBheWxvYWQ=",
    )
    assert envelope.header.backup_id == "bk_001"
    assert envelope.header.kdf_iterations == 100_000
    assert envelope.ciphertext_b64 is not None


def test_connector_and_webhook_records() -> None:
    config = ConnectorConfig(
        connector_id="conn_slack_01",
        name="Slack Production Alerts",
        connector_type=ConnectorType.SLACK,
        target_url="https://hooks.slack.com/services/T00/B00/X00",
        auth_token="xoxb-secret-token",
        status=ConnectorStatus.ACTIVE,
    )
    assert config.connector_type == ConnectorType.SLACK
    assert config.status == ConnectorStatus.ACTIVE

    delivery = WebhookDeliveryRecord(
        delivery_id="del_001",
        connector_id="conn_slack_01",
        event_id="evt_100",
        event_type="TASK_COMPLETED",
        status_code=200,
        success=True,
        latency_ms=45.2,
        attempt=1,
    )
    assert delivery.success is True
    assert delivery.status_code == 200
