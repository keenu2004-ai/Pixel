# ADR-0017: Edge AI Swarm Deployment & Autonomous Fleet Operations

## Status
Accepted

## Context
PIXEL previously supported multi-device pairing, device PKI, presence heartbeats, wake arbitration, and multimodal perception (Phases 0–16). However, computation was largely monolithic or statically assigned to the primary workstation. 

To enable seamless distributed edge AI execution across phones, laptops, desktops, edge servers, and embedded nodes without compromising security, PIXEL requires an intelligent, multi-signal fleet coordination layer that dynamically places perception, inference, tools, and bounded autonomous missions across trusted nodes.

## Decision

### 1. Central Authority Principle
Computation and perception may be distributed across edge nodes, but **unrestricted authority is never distributed**. The Central Authority (Primary Desktop Core) strictly maintains:
- Cryptographic identity and device trust state
- L6 Policy Gate enforcement
- L8 Verification of actions
- High-risk tool authorizations
- Memory authority and right-to-forget tombstones
- Model catalog governance and distribution signatures
- Fleet membership, quarantines, and permanent revocations
- Global emergency kill switches

Edge nodes are restricted to: `OBSERVE`, `COMPUTE`, `PROPOSE`, `EXECUTE ALLOWLISTED LOW-RISK TASKS`, and `REPORT`.

### 2. Multi-Signal Routing Engine
Every workload placement decision evaluates:
- **Capability Requirements**: GPU, NPU, Local STT/TTS, Vision, Browser, Git, etc.
- **5-Tier Privacy Classification**:
  - `PUBLIC`: Any active edge node.
  - `LOW_SENSITIVITY`: General non-personal tasks.
  - `PERSONAL`: User preferences, habits, tone.
  - `SENSITIVE`: Authenticated session data, private documents.
  - `HIGHLY_SENSITIVE`: Passwords, keys, OTPs, biometric data (**strictly requires local execution tier**).
- **Latency Budgets**: End-to-end network RTT + inference latency vs local execution.
- **Battery & Thermal State**: Battery <20% triggers automatic offloading to desktop/server; thermal throttling prevents heavy model placement.
- **Network Conditions**: Offline nodes retain safe local capabilities while remote-only tasks report graceful degradation.

### 3. Task Leases, Idempotency & Bounded Delegation
- Task execution authority is exclusively granted via time-bounded `TaskLease` objects.
- Consequential actions require unique `idempotency_key` records to prevent duplicate actions upon retries.
- Autonomous fleet missions enforce a hard limit on delegation depth (`max_delegation_depth <= 3`) with anti-escalation validation to prevent unbounded delegation loops.

### 4. Verified Model Distribution & Rollback
- Edge models are packaged in signed `ModelDistributionPackage` envelopes verified via SHA-256 checksums.
- Automated rollback replaces failing models with safe fallback baselines upon regression or hallucination spikes.

## Consequences

### Positive
- Heavy LLM/Vision workloads are dynamically offloaded to powerful servers/desktops, saving mobile battery.
- Voice/STT perception and sensitive credential handling remain strictly on-device, preserving user privacy and low latency.
- Resilience against worker crashes, network partitions, and malicious node spoofing.

### Negative / Trade-offs
- Slight overhead (<2ms) for multi-signal routing calculations and cryptographic lease handshakes.
- Requires network synchronization of vector clocks and tombstones for distributed memory consistency.
