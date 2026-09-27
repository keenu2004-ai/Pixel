# ADR 0010: Production Control Plane Architecture, Containerization & Full-Stack Hardening

## Status
Accepted

## Context
PIXEL requires a unified administrative and operational interface to monitor, observe, inspect, and control its full distributed runtime across desktop, mobile, satellite nodes, and backend services.
Without a hardened control plane architecture:
1. Operators and users have no unified visibility into active voice conversations, multi-device topologies, episodic/semantic memory, and autonomous task execution.
2. Administrative dashboards risk becoming disconnected secondary sources of truth or creating unauthenticated bypasses around the L6 Policy Engine and L8 Verification.
3. Real-time updates relying on naive polling degrade backend performance and introduce race conditions.
4. Unprotected control endpoints present high-severity attack vectors for privilege escalation, cross-site request forgery (CSRF), cross-site scripting (XSS), and data leakage.
5. Inconsistent containerization and environment configuration prevent reliable, reproducible deployments across platforms.

## Decision
We implement an **Authoritative Production Control Plane & Hardened Full-Stack Architecture**:

1. **Non-Authoritative Administrative Surface**:
   - The Control Plane (`ControlPlaneManager`) acts strictly as an administrative lens and operational coordinator over canonical PIXEL subsystems (`DeviceRegistry`, `PresenceManager`, `AutonomousScheduler`, `AutonomousWorkflowEngine`, `BudgetManager`, `GoalDriftDetector`, `MemoryManager`, `AgentPolicyGate`, and `VoiceGateway`).
   - The dashboard does not maintain independent authoritative state; all actions translate to validated runtime calls.

2. **Hierarchical Cryptographic RBAC & Token Authentication**:
   - Roles: `VIEWER` (read-only telemetry), `OPERATOR` (task execution, scheduling, memory search), `ADMIN` (approvals, memory purge, device revocation, role management), `SYSTEM` (internal service coordination).
   - Passwords hashed using PBKDF2-HMAC-SHA256 with 100,000 iterations and cryptographically random per-user salts.
   - HMAC-SHA256 signed access tokens with millisecond expiration timestamps and revocation ledger tracking.
   - Strict server-side policy enforcement on all REST and WebSocket routes via FastAPI dependency injection (`require_role`).

3. **Real-Time WebSocket Streaming & Event Bus Bridge**:
   - Authenticated WebSocket endpoint (`/ws/control-plane`) with connection lifecycle management, heartbeat ping/pong, and role-based stream filtering.
   - Bounded client output queues (1,000 max events) with automated drop-oldest overflow defense to prevent slow-client backpressure on core runtime threads.
   - Automatic subscription to runtime `EventBus` broadcasts (`TASK_UPDATED`, `TASK_APPROVED`, `TASK_CANCELLED`, `SCHEDULER_JOB_REGISTERED`, `MEMORY_STORED`, `DEVICE_REGISTERED`, `PRESENCE_HEARTBEAT`).

4. **Zero Security Bypass for Approvals & Actions**:
   - All high-impact administrative actions (task execution, memory forgetting, device revocation) pass through L6 `AgentPolicyGate` and L8 `ActionVerifier`.
   - Frontend provides an interactive Approval Card modal to satisfy cryptographic approvals without bypassing policy requirements.
   - Strict Content Security Policy (CSP), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and sanitize-by-default output formatting.

5. **Production Containerization & Multi-Stage Builds**:
   - Multi-stage Dockerfile based on `python:3.12-slim` executing under a non-root system user (`pixeluser:10001`).
   - Containerized healthcheck probe (`/health` responding `< 10ms` with system readiness metrics).
   - Docker Compose configuration with resource limits, health dependencies, and persistent data volumes.
   - Cross-platform startup automation scripts (`start_production.sh`, `start_production.ps1`).

6. **Native Design System Adherence**:
   - Dark-mode-first SPA UI built with semantic HTML5 and Vanilla CSS strictly implementing the design tokens defined in `docs/design-system.md` (`#0b0f19` Obsidian background, `#6366f1` Indigo accent, `#10b981` Emerald success, `#ef4444` Crimson alert).
   - Dynamic Canvas-based VoiceOrb visualizer for real-time conversation state indication.
   - Zero external third-party CDN or runtime framework dependencies.

## Consequences
- Operators gain real-time, low-latency ($<0.05\text{ms}$ bus dispatch, $<1\text{ms}$ API response) operational visibility and control.
- Security boundaries are strictly maintained: no direct database mutation, no secret leakage, and no role escalation.
- Deployments are fully reproducible, self-healing, and resilient across Windows, Linux, and container environments.
