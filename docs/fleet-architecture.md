# PIXEL Fleet Architecture & Topology

## 1. Fleet Membership & Lifecycle State Machine

Nodes within the PIXEL fleet transition through explicit cryptographic lifecycle states:

```
[DISCOVERED] ---> [PAIRING] ---> [AUTHENTICATING] ---> [TRUSTED] ---> [ACTIVE]
                                                          |              |
                                                          v              v
                                                     [QUARANTINED]  [DEGRADED]
                                                          |              |
                                                          v              v
                                                      [REVOKED]     [OFFLINE]
```

- **DISCOVERED**: Node broadcast detected via mDNS/BLE.
- **PAIRING**: User confirms 6-digit numeric comparison code.
- **AUTHENTICATING**: Mutual TLS handshake with PKI certificates issued by Central Authority.
- **TRUSTED**: Certificate validated, capabilities recorded.
- **ACTIVE**: Node actively sending telemetry heartbeats (default 30s interval) and eligible for task delegation.
- **DEGRADED**: Missing heartbeats or thermal throttling detected; only low-impact tasks placed.
- **OFFLINE**: Stale heartbeat timeout (>30s) or explicit disconnect; task leases revoked and reconciled.
- **QUARANTINED**: Misbehaving node isolated; active leases cancelled.
- **REVOKED**: Certificate revoked in PKI CRL; permanently blocked from re-enrolling.

## 2. Distributed Task Placement & Leases

Every delegated task is packaged into a cryptographically signed `DelegatedTaskEnvelope`:
```python
DelegatedTaskEnvelope(
    task_id="...",
    source_node_id="primary_desktop_core",
    target_node_id="phone_pixel_01",
    goal_description="Transcribe audio stream",
    capability_required=FleetCapability.LOCAL_STT,
    data_classification=FleetDataClassification.PERSONAL,
    idempotency_key="idempotency_run_01",
    max_delegation_depth=3,
    current_delegation_depth=1,
)
```

- **Exclusive Leases**: A worker acquires a `TaskLease` granting exclusive authority for a time window (e.g., 30s).
- **Checkpoints**: Workers periodically record `DistributedTaskCheckpoint` objects containing progress payloads.
- **Attestation**: On completion, worker returns `WorkerResultAttestation` verified by Central Authority before closing task.
