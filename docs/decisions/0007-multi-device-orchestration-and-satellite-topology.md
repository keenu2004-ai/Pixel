# ADR 0007: Multi-Device Orchestration, mTLS Topology & Satellite Audio Arbitration

## Status
Accepted (Source of Truth)

## Context
PIXEL operates across multiple client nodes (PC Workstation, Android Phone, Voice Satellites, Headless Agents).
Multi-device coordination introduces key distributed systems challenges:
1. **Device Identity & Trust**: Devices must have cryptographic identities (mTLS / Asymmetric Key Pairs) rather than relying on LAN presence or IP addresses.
2. **Explicit Pairing**: A remote device cannot silently become trusted. Pairing requires explicit user approval, short code/nonce exchange, and certificate provisioning.
3. **Multi-Microphone Wake Arbitration**: When multiple devices (e.g. phone in pocket + PC on desk + satellite on ceiling) hear `"Hey Pixel"`, only ONE device must respond. Duplicate task executions and audio feedback loops must be strictly prevented.
4. **Context & Task Handoff**: A user commanding a task on mobile ("Start preparing the report") must be able to continue on PC ("Continue on my PC") with atomic concurrency control, scoped context (no secret leaking), and un-tampered L6 approval preservation.
5. **No Split-Brain Authority**: PIXEL Core remains the central state and policy authority. Devices cannot independently redefine policy or fork task state.

## Decision
1. Implement `DeviceIdentity` and `DevicePresenceRecord` with typed capabilities (`DeviceCapability`) and roles (`DeviceRole`).
2. Implement `PKIEngine` for mTLS certificate generation, validation, and cryptographic device revocation.
3. Implement `DeviceRegistry` & `PresenceManager` with bounded heartbeats and stale-device auto-detection.
4. Implement `WakeArbiter` with multi-signal score ranking (interaction ownership, SNR, confidence, RTT) and deduplication window.
5. Implement `HandoffManager` with optimistic concurrency leasing (`concurrency_lease_token`, `task_version`) and scoped context transfer.
6. Provide deterministic mock node emulators (`MockPCNode`, `MockAndroidNode`, `MockSatelliteNode`) for 100% CI automation.

## Consequences
- **Positive**: Seamless multi-room, multi-device ecosystem with zero duplicate responses; robust security boundary where satellites cannot bypass core L6 policy; atomic task migration across screens and speakers.
- **Trade-offs**: Requires periodic heartbeat messages (30s) to maintain accurate presence telemetry.
