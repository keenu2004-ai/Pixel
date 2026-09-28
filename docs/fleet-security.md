# PIXEL Fleet Security & Threat Model

## 1. Zero-Trust Fleet Model

No edge node is intrinsically trusted merely by presence on a local network. All fleet interactions are governed by cryptographic identity, time-bounded capabilities, and explicit policy validation.

```
USER
  │
  ▼
CENTRAL AUTHORITY (Primary Core)
  ├── PKI Certificate Authority & Device Registry
  ├── L6 Policy Engine (Hard risk-class constraints)
  ├── L8 Action Verifier (Post-execution integrity check)
  └── Memory & Model Governance
  │
  ▼ (Mutual TLS + Signed Envelopes)
EDGE RUNTIME NODES (Phone, GPU Server, Secondary PC)
  ├── Bounded Tool Execution Sandbox
  ├── Local AI Inference Runtime
  └── Heartbeat & Resource Telemetry Agent
```

## 2. Adversarial Threat Mitigations

| Threat Vector | Mitigation Mechanism | Verification Test |
|---|---|---|
| **Node Spoofing** | Mutual TLS PKI verification; only 1 central authority permitted per fleet. | `test_adversarial_revoked_node_execution_defense` |
| **Replay Attacks** | Unique `idempotency_key` and nonce validation for all consequential actions. | `test_fleet_scheduler_lifecycle` |
| **Stale Lease Exploitation** | Time-bounded `expires_at` on leases; results submitted on expired leases are rejected. | `test_adversarial_stale_lease_rejection` |
| **Swarm Escalation / Infinite Loops** | Hard maximum delegation depth (`max_delegation_depth <= 3`) verified by `AutonomousFleetMissionGovernor`. | `test_adversarial_delegation_escalation_depth_defense` |
| **Credential & OTP Leakage** | 5-tier classification; `HIGHLY_SENSITIVE` data strictly pinned to `LOCAL` tier. | `test_adversarial_highly_sensitive_privacy_leak_defense` |
| **Model Poisoning / Substitution** | SHA-256 integrity hash verification and signed distribution packaging. | `test_tampered_model_checksum_rejection` |
| **Fleet Compromise Lockdown** | 6 fleet kill switch domains (`ALL_EDGE_EXECUTION`, `REMOTE_INFERENCE`, `MEMORY_SYNC`, etc.) | `test_adversarial_fleet_kill_switch_enforcement` |
