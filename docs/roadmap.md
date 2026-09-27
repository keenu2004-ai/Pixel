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

### Phase 6: Android Native Assistant (VoiceInteractionService) (ACTIVE MILESTONE)
- **Scope**:
  - Android `VoiceInteractionService` implementation, Role Manager default assistant registration, and background persistent daemon.
- **Exit Condition**: Replaces system assistant on Android device; handles native voice invocation with screen turned off.

### Phase 7: Multi-Device Orchestration & Satellite Topology
- **Scope**:
  - mTLS device pairing, presence registry, and context handoff between PC and phone.
- **Exit Condition**: Alarm commanded from PC rings on Android phone if user is away from keyboard.

### Phase 8: Custom Voice Cloning & Personalized Local Models
- **Scope**:
  - Few-shot speaker embedding, Indian accent personalization, quantized 4-bit local intent models (Qwen/Llama).
- **Exit Condition**: Custom cloned voice synthesizes Hindi/English naturally on local hardware.

### Phase 9: Proactive & Autonomous Workflows
- **Scope**:
  - Event-driven background monitors, scheduled long-running agents with safety checkpoints.
- **Exit Condition**: Autonomous tasks run reliably without unconstrained drift.
