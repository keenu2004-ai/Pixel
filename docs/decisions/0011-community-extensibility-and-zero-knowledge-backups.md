# ADR 0011: Community Extensibility, Sandboxing, Zero-Knowledge Backups, and Enterprise Connectors

## Status
**ACCEPTED** (Phase 11 Architectural Standard)

## Context
PIXEL is evolving from a single-user personal AI runtime into an extensible personal AI platform capable of executing third-party plugins, community skills, syncing encrypted data across nodes, and communicating with external enterprise services (Slack, Discord, Home Assistant, Matrix). 

Executing untrusted third-party code and transmitting data across networks introduces severe security risks:
1. **Malicious Sandbox Escape & Secret Theft**: Third-party plugins attempting to read environment secrets, private keys, database credentials, or host filesystem files.
2. **Supply-Chain Attacks & Privilege Escalation**: Community marketplace skills silently escalating privileges across version updates or attempting dynamic code execution (`eval`, `exec`, `subprocess`).
3. **Storage Compromise & Plaintext Memory Exposure**: Cloud backup storage operators or compromised intermediate servers reading user facts, semantic memory, or device topologies.
4. **SSRF & Cascading Webhook Loops**: Outbound enterprise connectors attacking cloud metadata services (e.g. AWS `169.254.169.254`), internal subnets, or entering infinite self-triggering event loops.

## Decisions

### 1. Strongly Typed Sandboxed Subprocess Runtime
- **Subprocess Isolation Driver (`SubprocessSandboxDriver`)**: Plugins execute in isolated child processes with a strictly purged environment (`env={}`) containing zero host secret variables (`PIXEL_DATABASE_PASSWORD`, API keys).
- **JSON-RPC IPC**: Inter-process communication operates exclusively over standard I/O using typed JSON-RPC envelopes with bounded 1MB buffers.
- **Resource Governance**: Wall-clock execution timeouts (default 5s, configurable per request) and automatic process tree termination prevent runaway CPU/memory resource exhaustion.
- **Zero Default Capabilities**: Plugins receive no capabilities by default. Permissions (`read_conversation`, `write_memory`, `network_outbound`, `device_control`, `tool_invocation`) are explicit, minimal, auditable, and revocable.

### 2. Verified Community Skill Marketplace & Static AST Vetting Pipeline
- **AST Security Vetting (`SkillVettingPipeline`)**: Before any community skill can be published or installed, an automated Python AST scanner inspects source files. It unconditionally rejects dangerous execution primitives (`eval`, `exec`, `compile`, `__import__`, `subprocess`, `os.system`, `os.popen`, `ctypes`, `pty`) and regex-scans for exposed secrets.
- **Non-Bypassable L6 Policy & L8 Verification**: Community skills are registered into `ToolRegistry` via `CommunitySkillBridge`. Execution MUST pass through `AgentPolicyGate` (L6) and `ActionVerifier` (L8) before invoking the sandbox.
- **Privilege Expansion Detection**: Version updates that request newly added capabilities are automatically quarantined in `INSTALLED` state pending explicit administrator re-approval.
- **Emergency Revocation Ledger**: Revoked plugins immediately terminate all running worker processes and update an append-only cryptographic ledger (`pixel_plugins.db`), preventing execution even across system reboots.

### 3. Zero-Knowledge Client-Side Encrypted Backup Synchronization
- **Cryptographic Primitives**: Backups are encrypted before leaving the client runtime using AES-256-GCM with 96-bit nonces, 128-bit authentication tags, and PBKDF2-HMAC-SHA256 (100,000 iterations).
- **Additional Authenticated Data (AAD)**: Envelope headers (`backup_id`, `user_id`, `device_id`, `scope`, `revision`) are bound directly into the AES-GCM AAD context. Any tampering with metadata causes immediate fail-closed decryption failure.
- **Zero Plaintext Storage (`ZeroKnowledgeBackupStorage`)**: The persistence layer stores only opaque encrypted envelopes and metadata views (`BackupMetadataView`); it possesses zero key material and cannot decrypt user memory or device configs.

### 4. Outbound Webhook Engine and Enterprise Connectors
- **Unified Connector Contract (`BaseConnector`)**: Outbound integrations (Slack, Discord, Home Assistant, Matrix) adhere to a unified base contract with payload adaptation, HMAC-SHA256 request signing, and token-bucket rate limiting.
- **SSRF Defense**: Connectors validate target destination URLs, rejecting loopback (`127.0.0.1`), private networks (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), and link-local cloud metadata endpoints (`169.254.169.254`).
- **Physical Safety Classification**: Home Assistant connector classifies actions by physical risk; high-impact operations (e.g. unlocking front doors, opening gates) require mandatory L6 confirmation.
- **Loop Prevention & Audit Ledger**: `WebhookEngine` enforces a hop limit counter (`MAX_HOP_COUNT = 3`) to terminate recursive event echoes, and logs delivery telemetry into `pixel_connectors.db`.

## Consequences
- **Security Invariant**: Third-party extensions are strictly subordinate to PIXEL's core L6 Policy and L8 Verification architectures.
- **Zero-Knowledge Privacy**: Cloud or remote storage compromises yield only encrypted ciphertext blobs.
- **Deterministic Latency**: Subprocess sandbox execution averages ~50-80ms; AST security vetting completes in <1ms; client AES-256-GCM backup throughput is <50ms.
- **Control Plane Visibility**: Full-stack administration and RBAC (`READ_ONLY`, `OPERATOR`, `ADMIN`) provide real-time visibility into plugins, vetting reports, backup envelopes, and webhook deliveries.
