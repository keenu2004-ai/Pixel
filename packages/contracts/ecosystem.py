"""
PIXEL Community Ecosystem & Extensibility Hub Contracts (Phase 11).

Defines strongly-typed Pydantic contracts for:
1. Sandboxed Plugins, Capabilities, Risk Classes, and Lifecycle States.
2. Verified Community Skill Manifests, Security Findings, and Vetting Reports.
3. Zero-Knowledge End-to-End Encrypted Backup Envelopes and Restoration.
4. Outbound Webhook Engine, Enterprise Connectors, and Delivery Audits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# 1. Plugin & Capability Contracts
# ============================================================================


class PluginCapability(StrEnum):
    """Explicit capabilities requestable by third-party plugins."""

    READ_CONVERSATION = "read_conversation"
    WRITE_CONVERSATION = "write_conversation"
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    NETWORK_OUTBOUND = "network_outbound"
    DEVICE_READ = "device_read"
    DEVICE_CONTROL = "device_control"
    TOOL_INVOCATION = "tool_invocation"
    WEBHOOK_EMIT = "webhook_emit"
    SYSTEM_NOTIFICATION = "system_notification"


class PluginRiskClass(StrEnum):
    """Risk tier of a plugin or capability."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PluginLifecycleState(StrEnum):
    """Lifecycle states of an extension/plugin."""

    DISCOVERED = "discovered"
    VERIFIED = "verified"
    APPROVED = "approved"
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    REVOKED = "revoked"
    QUARANTINED = "quarantined"
    UNINSTALLED = "uninstalled"


class PluginRuntimeType(StrEnum):
    """Execution sandbox environment type."""

    SUBPROCESS_SANDBOX = "subprocess_sandbox"
    WASM_SANDBOX = "wasm_sandbox"


class PluginPermissionGrant(BaseModel):
    """An explicit permission granted to a plugin by an administrator."""

    capability: PluginCapability
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    granted_by: str = "admin"
    scope_constraints: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class PluginManifest(BaseModel):
    """Immutable contract defining a third-party plugin package."""

    plugin_id: str
    name: str
    version: str
    publisher: str
    description: str
    runtime: PluginRuntimeType = PluginRuntimeType.SUBPROCESS_SANDBOX
    entrypoint: str  # e.g., "main.py" or "entry.wasm"
    capabilities: list[PluginCapability] = Field(default_factory=list)
    risk_class: PluginRiskClass = PluginRiskClass.LOW
    dependencies: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    min_pixel_version: str = "1.0.0"
    max_pixel_version: str | None = None
    integrity_sha256: str
    signature: str | None = None
    publisher_public_key: str | None = None

    model_config = ConfigDict(extra="forbid")


class PluginExecutionRequest(BaseModel):
    """Request to execute a function/tool within a sandboxed plugin."""

    plugin_id: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_sec: float = 10.0
    memory_limit_mb: int = 128
    caller_id: str = "system"
    request_id: str = Field(default_factory=lambda: datetime.now(UTC).strftime("%Y%m%d%H%M%S%f"))


class PluginExecutionResult(BaseModel):
    """Structured response from sandboxed plugin execution."""

    plugin_id: str
    action: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    memory_used_mb: float = 0.0
    request_id: str


# ============================================================================
# 2. Skill Vetting & Marketplace Contracts
# ============================================================================


class VettingState(StrEnum):
    """Security vetting state of a community skill."""

    PENDING = "pending"
    SCANNING = "scanning"
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"


class FindingSeverity(StrEnum):
    """Severity of a security finding in static/AST analysis."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityFinding(BaseModel):
    """A specific vulnerability or suspicious pattern detected during vetting."""

    code: str
    severity: FindingSeverity
    message: str
    file: str | None = None
    line: int | None = None
    rule_id: str

    model_config = ConfigDict(frozen=True)


class SkillVettingReport(BaseModel):
    """Comprehensive automated security evaluation report for a skill."""

    manifest_id: str
    state: VettingState
    findings: list[SecurityFinding] = Field(default_factory=list)
    vetted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scanner_version: str = "1.0.0"
    passed: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class CommunitySkillManifest(BaseModel):
    """Manifest for a verified community skill exposed to the Agent Runtime."""

    skill_id: str
    publisher: str
    version: str
    display_name: str
    description: str
    triggers: list[str] = Field(default_factory=list)  # Wake phrases or intent keywords
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[PluginCapability] = Field(default_factory=list)
    tool_dependencies: list[str] = Field(default_factory=list)
    runtime_requirements: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None
    vetting_report: SkillVettingReport | None = None

    model_config = ConfigDict(extra="forbid")


class MarketplaceListing(BaseModel):
    """Public marketplace catalog item representation."""

    skill: CommunitySkillManifest
    downloads_count: int = 0
    rating: float = 5.0
    verified: bool = False
    featured: bool = False
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SkillInstallRequest(BaseModel):
    """Request to install a community skill."""

    skill_id: str
    version: str | None = None
    accepted_capabilities: list[PluginCapability] = Field(default_factory=list)
    auto_enable: bool = True


class SkillUpdateRequest(BaseModel):
    """Request to update an existing community skill."""

    skill_id: str
    target_version: str
    acknowledge_new_capabilities: bool = False


# ============================================================================
# 3. Zero-Knowledge Encrypted Backup Contracts
# ============================================================================


class BackupScope(StrEnum):
    """Scope of data included in an encrypted backup snapshot."""

    ALL = "all"
    MEMORY_ONLY = "memory_only"
    DEVICE_CONFIG_ONLY = "device_config_only"
    EPISODIC_ONLY = "episodic_only"
    SEMANTIC_ONLY = "semantic_only"


class BackupHeader(BaseModel):
    """Unencrypted envelope header containing sync metadata (zero plaintext)."""

    format_version: str = "1.0.0"
    backup_id: str
    user_id: str
    device_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revision: int = 1
    scope: BackupScope = BackupScope.ALL
    kdf_salt: str  # Hex encoded salt for PBKDF2
    kdf_iterations: int = 100_000
    nonce: str  # Hex encoded 96-bit AES-GCM nonce
    auth_tag: str  # Hex encoded 128-bit AES-GCM authentication tag
    ciphertext_sha256: str  # SHA-256 integrity hash of ciphertext blob

    model_config = ConfigDict(frozen=True)


class EncryptedBackupEnvelope(BaseModel):
    """Zero-knowledge encrypted backup payload."""

    header: BackupHeader
    ciphertext_b64: str  # Base64 encoded AES-256-GCM ciphertext of compressed JSON payload


class BackupMetadataView(BaseModel):
    """Safe metadata representation for UI and control plane inspection."""

    backup_id: str
    user_id: str
    device_id: str
    timestamp: datetime
    revision: int
    scope: BackupScope
    size_bytes: int
    ciphertext_sha256: str


class BackupRestoreRequest(BaseModel):
    """Request to decrypt and restore a backup envelope."""

    backup_id: str
    passphrase: str
    target_scope: BackupScope | None = None
    override_conflicts: bool = False


class BackupRestoreResult(BaseModel):
    """Result summary of a backup restore operation."""

    backup_id: str
    success: bool
    restored_items_count: int = 0
    memory_facts_restored: int = 0
    devices_restored: int = 0
    error: str | None = None
    duration_ms: float = 0.0


# ============================================================================
# 4. Outbound Webhook & Enterprise Connector Contracts
# ============================================================================


class ConnectorType(StrEnum):
    """Supported connector destinations."""

    SLACK = "slack"
    DISCORD = "discord"
    HOME_ASSISTANT = "home_assistant"
    MATRIX = "matrix"
    GENERIC_WEBHOOK = "generic_webhook"


class ConnectorStatus(StrEnum):
    """Operational status of an outbound connector."""

    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    REVOKED = "revoked"


class ConnectorConfig(BaseModel):
    """Configuration contract for an outbound connector."""

    connector_id: str
    name: str
    connector_type: ConnectorType
    target_url: str
    auth_token: str | None = None
    signing_secret: str | None = None
    enabled_events: list[str] = Field(default_factory=lambda: ["*"])
    rate_limit_per_min: int = 60
    max_retries: int = 3
    timeout_sec: float = 5.0
    status: ConnectorStatus = ConnectorStatus.ACTIVE
    extra_headers: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutboundWebhookPayload(BaseModel):
    """Structured signed outbound payload dispatched to external webhook endpoints."""

    delivery_id: str
    event_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None
    hop_count: int = 0


class WebhookDeliveryRecord(BaseModel):
    """Audit log entry for an outbound webhook attempt."""

    delivery_id: str
    connector_id: str
    event_id: str
    event_type: str
    status_code: int | None = None
    success: bool
    latency_ms: float
    attempt: int
    error_message: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
