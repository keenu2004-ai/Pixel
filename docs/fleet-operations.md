# PIXEL Fleet Operations & Observability

## 1. Operator Control Plane Endpoints

The PIXEL Control Plane provides unified REST and WebSocket endpoints for fleet observability and administration under `/api/v1/fleet`:

- `GET /api/v1/fleet/nodes`: List registered nodes, active status, resources, and hardware profiles.
- `POST /api/v1/fleet/nodes/enroll`: Securely enroll a new device with PKI certificates.
- `POST /api/v1/fleet/nodes/{node_id}/heartbeat`: Ingest telemetry, battery percentage, thermal state, and network health.
- `POST /api/v1/fleet/nodes/{node_id}/quarantine`: Immediately isolate a misbehaving or suspicious node.
- `POST /api/v1/fleet/nodes/{node_id}/revoke`: Permanently revoke a device's certificate and access.
- `GET /api/v1/fleet/models`: Query distributable AI models and edge cache state.
- `POST /api/v1/fleet/route`: Request multi-signal routing calculation with full explanation.
- `POST /api/v1/fleet/delegate`: Dispatch a signed task envelope to an edge node.
- `POST /api/v1/fleet/cancel`: Cancel an active delegated task and revoke its lease.
- `GET /api/v1/fleet/killswitches`: View status of emergency fleet kill switches.
- `POST /api/v1/fleet/killswitches/activate`: Engage emergency shutdown for a specific domain.

## 2. Distributed Memory Coordination

- **Bounded Replication**: Verified user preferences and active goals are replicated across trusted devices.
- **Vector Clocks**: Fact updates carry monotonic version clocks (`ver >= current_ver`) to resolve cross-device merge conflicts.
- **Right-to-Forget Deletion Tombstones**: Deleting a fact or revoking a node propagates a persistent tombstone, immediately purging records across all node caches upon reconnection.
