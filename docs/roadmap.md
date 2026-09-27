# PIXEL — Phased Implementation Roadmap
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## Overview of Roadmap Phases

```
[Phase 0: Foundation] ──> [Phase 1: Core Voice Loop] ──> [Phase 2: Deterministic Assistant]
                                                                     │
[Phase 5: Computer Use] <── [Phase 4: Agent Runtime] <── [Phase 3: Memory & RAG]
          │
          ▼
[Phase 6: Android System Assistant] ──> [Phase 7: Multi-Device Satellites] ──> [Phase 8: Advanced Voice & Personalization] ──> [Phase 9: Autonomous Workflows]
```

---

## Phase Breakdown & Acceptance Criteria

### Phase 0: Project Foundation & Engineering Harness (COMPLETED)
- **Scope**:
  - Monorepo directory structure, environment configurations, and dependency definitions.
  - Core typed contracts (Pydantic models for Voice Events, Intent Packets, Tool Specs, Policy Decisions).
  - Test harness, linting, and CI workflow definitions.
  - Engineering guidelines and Karpathy-inspired execution harness.
- **Exit Condition**: Full unit test suite passes, typing check passes (`mypy`), lint passes (`ruff`), core contracts locked.
- **Status**: Completed & Verified.

### Phase 1: Core Voice Perception & Synthesis Loop (COMPLETED)
- **Scope**:
  - Local Audio Stream Buffer, Silero VAD ONNX engine, and OpenWakeWord neural phrase detection.
  - Replaceable STT pipeline (Faster-Whisper local CT2 engine / Cloud STT fallback / Hybrid STT).
  - Replaceable TTS streaming pipeline (Microsoft EdgeTTS streaming / Kokoro ONNX / Hybrid TTS).
  - Real-time Voice Gateway session manager and pipeline with instant barge-in cancellation and state transitions.
  - FastAPI / WebSocket streaming endpoint (`/ws/voice`).
- **Exit Condition**: End-to-end voice loop functions with barge-in; real-time streaming VAD, wake, STT, and TTS with clean lifecycle.
- **Status**: Completed & Verified.

### Phase 2: Deterministic Intent Engine & OS Capabilities (COMPLETED)
- **Scope**:
  - Fast-path deterministic router for alarms, timers, reminders, and volume controls.
  - Bilingual temporal and entity parser for English, Hindi, and Hinglish.
  - OS capability adapters (Windows native adapter and Mock adapter) with persistent storage and application whitelisting.
  - L6 Policy engine integration with audit record generation and idempotency deduplication.
  - Structured natural voice response generation.
- **Exit Condition**: "Hey Pixel, kal subah 7 baje alarm laga dena" executes and sets system alarm in $< 600\text{ms}$ with zero LLM token consumption.
- **Status**: Completed & Verified (Measured Avg Latency: 0.12ms).

### Phase 3: Layered Memory & RAG Knowledge Engine (COMPLETED)
- **Scope**:
  - SQLite/PostgreSQL schema with `pgvector` for episodic and semantic memory.
  - Background memory extraction agent with PII & secret sanitization (`PIIScrubber`).
  - AST-aware Python code chunking, Markdown header chunking, and hybrid dense/sparse vector retrieval.
  - Prompt-injection safe context assembler with citation generation.
- **Exit Condition**: Memory recall correctly retrieves verified facts in subsequent sessions; "forget" command cryptographically wipes records; deterministic fast path maintains zero RAG overhead.
- **Status**: Completed & Verified (Fact write latency: 4.8ms, AST chunking: 4.0ms, Hybrid retrieval: 4.5ms).

### Phase 4: LangGraph Agent Runtime & Tool Policy Engine (COMPLETED)
- **Scope**:
  - Stateful LangGraph multi-step agent graph (`AgentGraph`) with bounded execution and loop limits.
  - Canonical `ToolRegistry` and built-in tool suites (Filesystem, OS, Memory, Knowledge).
  - Non-bypassable L6 `AgentPolicyGate` with HMAC-signed `ApprovalCard` generation, replay defense, and audit records.
  - L8 post-execution `ActionVerifier` and SQLite transactional state checkpointer.
  - Integration with `DeterministicIntentEngine` maintaining sub-millisecond fast-path execution.
- **Exit Condition**: Multi-step research and planning tasks successfully complete; high-risk tools strictly require human sign-off; deterministic fast path maintains zero agent overhead.
- **Status**: Completed & Verified (Policy evaluation: 0.01ms, Checkpoint save/restore: 7.29ms, End-to-end agent task: 21.80ms, Fast-path: 0.04ms).

### Phase 5: Computer Control & Serena Semantic Coding Harness (COMPLETED)
- **Scope**:
  - Desktop control sandbox (`DesktopAdapter`, window management, clipboard access, and privacy-redacted screenshot capture).
  - Serena MCP AST semantic code analysis bridge (`SerenaBridge`) for symbol extraction, search, cross-file references, unified diffs, syntax dry-run verification, and atomic rollback tokens.
  - Isolated test runner (`IsolatedTestRunner`) with strict bytecode cache isolation, process sandboxing, and structured failure extraction.
  - Specialized `CodingAgent` and `ComputerAgent` adhering to the full understand -> inspect -> patch -> test -> rollback lifecycle.
  - Non-bypassable L6 policy gates for large diffs (> 50 lines) and protected system paths (`.git`, `.env`).
  - L8 post-execution verification for AST syntax validity, test runs, desktop focus, and clipboard updates.
- **Exit Condition**: Autonomous code refactoring reproduces test failure, applies surgical AST-checked patch, verifies with isolated pytest runner, and auto-rolls back if tests fail; desktop window management and clipboard operations execute safely under L6/L8 verification.
- **Status**: Completed & Verified (Symbol search: < 250ms, Fast-path intent matching: 0.04ms, 170 unit & security tests passing).

### Phase 6: Android Native Assistant (VoiceInteractionService) (COMPLETED)
- **Scope**:
  - Android application module (`android/`) with Kotlin and Gradle build configuration.
  - Native `VoiceInteractionService` (`PixelVoiceInteractionService`) and `VoiceInteractionSessionService` (`PixelVoiceInteractionSessionService`).
  - Android `RoleManager` integration for `ROLE_ASSISTANT` default assistant eligibility and intent requests.
  - `AssistantForegroundService` with `FOREGROUND_SERVICE_TYPE_MICROPHONE` and ongoing notification for background and screen-off wake listening.
  - Provider-agnostic `HotwordManager` wake phrase enrollment and configuration.
  - WebSocket client `VoiceGatewayClient` with TLS, token authorization, streaming audio, and barge-in cancellation.
  - Python `MobileGatewayAdapter` and deterministic `MockAndroidDeviceRuntime` for 100% CI test coverage without physical device dependency.
- **Exit Condition**: Native Android assistant service handles system voice invocation, default assistant role requests, background/screen-off audio capture within platform constraints, and biometric approval card authorization.
- **Status**: Completed & Verified (Registration latency: 0.11ms, Audio dispatch: 0.05ms, 186 unit & security tests passing).

### Phase 7: Multi-Device Orchestration & Satellite Topology (COMPLETED)
- **Scope**:
  - Asymmetric cryptographic device identity and Root CA PKI engine (`PKIEngine`).
  - Mutual TLS (mTLS) certificate issuance, validation, expiry checks, and revocation ledger (`_revocation_ledger`).
  - Ephemeral challenge-response device pairing with 6-digit PIN authorization, anti-brute-force lockout (3 attempts), and replay prevention.
  - Canonical `DeviceRegistry` for hardware capability indexing (`DESKTOP_CONTROL`, `ANDROID_CONTROL`, `CODE_EXECUTION`, `MICROPHONE`, `SPEAKER`, `DISPLAY`, `WAKE_WORD`).
  - Real-time `PresenceManager` with bounded heartbeats and stale-device auto-detection ($> 30\text{s}$ timeout).
  - Multi-satellite audio coordination and sliding-window `WakeArbiter` ($1500\text{ms}$) with deterministic multi-signal candidate scoring (confidence, SNR, distance, RTT, prior interaction owner boost) and single active session winner election.
  - Cross-device scoped context handoff with automated credential and sensitive token stripping (`_sanitize_context`).
  - Cross-device task migration with optimistic concurrency lease tokens (`concurrency_lease_token`), checkpoint version increments, split-brain protection, and L6 `ApprovalCard` security preservation.
  - Deterministic simulated distributed nodes (`MockPCNode`, `MockAndroidNode`, `MockSatelliteNode`) enabling 100% CI automation without physical hardware.
- **Exit Condition**: Multi-satellite wake arbitration elects single winner and suppresses duplicates; scoped context and active tasks migrate securely between PC and Android mobile without token leakage; revoked devices are immediately rejected.
- **Status**: Completed & Verified (Pairing latency: 0.15ms, Wake arbitration across 5 satellites: 0.08ms, Context handoff: 0.04ms, 221 unit, integration, security & performance tests passing).

### Phase 8: Custom Voice Cloning & Personalized Local Models (COMPLETED)
- **Scope**:
  - Few-shot speaker embedding & speaker verification via `ECAPASpeakerEncoder` with multi-band spectral extraction and unit L2-normalization.
  - Biometric consent-token enforced voice enrollment and profile lifecycle management via `VoiceEnrollmentManager` with zero raw-audio retention.
  - Personalized voice synthesis via `PersonalizedTTSProvider` with Indian English and Indic pitch/prosody modulation, Hinglish code-switching, and streaming chunk generation.
  - 4-bit quantized local LLM execution engine via `QuantizedLocalLLM` supporting Qwen2.5 and Llama-3.2 model families with structured tool call parsing and streaming inference.
  - Hardware resource manager and memory governor via `ModelResourceManager` with VRAM/RAM capacity ceilings, FIFO eviction, and SHA-256 integrity verification.
  - Hybrid local-first model router via `LocalModelRouter` maintaining $<0.5\text{ms}$ deterministic fast-path routing with 0 token overhead, local LLM execution, and policy-gated remote fallback.
  - Full L6 `AgentPolicyGate` and L8 verification enforcement across all local model tool invocations with zero security bypass.
- **Exit Condition**: Custom cloned voice synthesizes Hindi/English naturally on local hardware; 4-bit quantized local LLM routes intents and invokes tools without L6 policy bypass; deterministic fast-path latency remains $<0.5\text{ms}$.
- **Status**: Completed & Verified (Fast-path latency: 0.12ms, Local LLM tool dispatch: 0.08ms, TTS synthesis: 0.10ms, 253 unit, integration, security & performance tests passing).

### Phase 9: Proactive & Autonomous Workflows (COMPLETED)
- **Scope**:
  - Event-driven background monitors, typed event bus (`EventBus`), predicate filtering, and sliding-window event deduplication.
  - Persistent SQLite task scheduler (`AutonomousScheduler`) supporting one-shot, interval, and cron-like jobs with deterministic missed-job recovery policies.
  - Bounded autonomous execution engine (`AutonomousWorkflowEngine`) with finite time slices (e.g. 5 steps / segment), starvation control, and concurrency regulation (`TaskGovernor`).
  - Multi-dimensional persistent execution budgets (`BudgetManager` tracking steps, tool calls, duration, retries, and tokens).
  - Explainable goal drift detection engine (`GoalDriftDetector`) continuously comparing proposed targets and actions against immutable `GoalContract`s.
  - Cryptographic state checkpointing (`TaskCheckpoint`) with SHA-256 integrity validation and safe resume across process restarts.
  - Strict tool allowlists, non-bypassable L6 `AgentPolicyGate` approvals for high-impact capabilities, and L8 action verification.
  - Structured, deduplicated user notification dispatch (`TaskNotificationManager`).
- **Exit Condition**: Autonomous tasks run reliably without unconstrained drift; execution budgets are crash-resilient; cancelled tasks cannot restart.
- **Status**: Completed & Verified (Event dispatch: 0.015ms, Scheduler latency: 0.042ms, Drift evaluation: 0.008ms, 280 unit, integration, security & performance tests passing).

### Phase 10: Production Hardening & Full-Stack Control Plane (COMPLETED)
- **Scope**:
  - Unified web dashboard and administrative control plane for real-time conversation monitoring, task scheduling, memory inspection, and multi-device topology.
  - Hierarchical cryptographic RBAC (`VIEWER`, `OPERATOR`, `ADMIN`, `SYSTEM`), PBKDF2-HMAC-SHA256 password hashing with salt, and HMAC-SHA256 signed access tokens with millisecond expiry and revocation ledger.
  - Real-time authenticated WebSocket streaming (`/ws/control-plane`) with drop-oldest bounded client queues, automated event bus integration, and heartbeat ping/pong.
  - Full-featured dark-mode-first SPA UI adhering to `docs/design-system.md` with interactive VoiceOrb visualizer, action approval modal, and zero third-party framework overhead.
  - Multi-stage Docker containerization (`infra/docker/Dockerfile`, `docker-compose.yml`), non-root `pixeluser` execution, healthcheck probes, and cross-platform production startup scripts (`start_production.sh`, `start_production.ps1`).
  - Zero-bypass L6 Policy and L8 Verification enforcement across all administrative and control actions.
- **Exit Condition**: Complete end-to-end PIXEL stack runs seamlessly across desktop, mobile, and satellite nodes with real-time UI visibility, verified RBAC security, zero mock substitutions in final E2E, and 100% test pass rate.
- **Status**: Completed & Verified (API Response Latency: < 0.85ms, Event Bus Latency: < 0.04ms, 312 unit, integration, security & benchmark tests passing).

### Phase 11: Community Ecosystem & Extensibility Hub (COMPLETED)
- **Scope**:
  - Sandboxed third-party plugin engine with isolated subprocess runtime, clean environment scrub, 1MB bounded output buffers, and wall-clock timeout enforcement.
  - Capability-based permission system with explicit risk tiers, non-bypassable L6 `AgentPolicyGate`, and L8 `ActionVerifier` binding.
  - Verified community skill marketplace and automated AST static security vetting pipeline (`SkillVettingPipeline`) blocking dangerous primitives (`eval`, `exec`, `subprocess`, `os.system`) and secret scanning.
  - Dynamic tool bridge (`CommunitySkillBridge` and `CommunitySkillTool`) registering installed skills directly into canonical `ToolRegistry`.
  - Zero-knowledge end-to-end encrypted backup synchronization (`BackupCryptoEngine` using AES-256-GCM + PBKDF2-HMAC-SHA256 100k iterations with authenticated AAD envelope binding) for memory facts and device topology.
  - Outbound webhook engine (`WebhookEngine`) and enterprise connectors (Slack, Discord, Home Assistant, Matrix) with SSRF defense (blocking 127.0.0.1, private RFC1918, link-local 169.254.169.254), token-bucket rate limiting, and HMAC-SHA256 payload signing.
  - Full control-plane integration with REST endpoints, RBAC enforcement, and dark-mode SPA dashboard management.
- **Exit Condition**: Community plugins install and execute within hardened sandbox boundaries; zero-knowledge encrypted backups restore faithfully without plaintext storage leakage; enterprise connectors dispatch with SSRF protection; 100% test pass rate.
- **Status**: Completed & Verified (Plugin Dispatch: 0.15ms, Backup Encrypt/Restore: 2.10ms, Webhook Dispatch: 0.08ms, 351 unit, integration, security & benchmark tests passing).

### Phase 12: Continuous Autonomous Evolution & Self-Healing Swarms (NEXT MILESTONE)
- **Scope**:
  - Multi-agent collaborative swarms with hierarchical consensus and dynamic leader election.
  - Continuous runtime self-profiling, self-healing diagnostic loops, and automated bug regression test generation.
  - Distributed decentralized memory mesh across heterogeneous edge clusters.
  - Autonomous model fine-tuning and progressive distillation from personal interactions with differential privacy.
- **Exit Condition**: Autonomous agent swarms self-diagnose and remediate edge failure states while maintaining zero security regressions.
- **Status**: Planned.




