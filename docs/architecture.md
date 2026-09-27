# PIXEL — Core Engineering & System Architecture
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## 1. High-Level Architectural Topology

PIXEL is designed as a **Layered, Event-Driven, Capability-Oriented System**.
The architecture cleanly separates hardware perception, stream routing, intent classification, agentic reasoning, policy-enforced execution, and persistent memory.

```
+-------------------------------------------------------------------------+
| L0: DEVICE RUNTIME (Mic, Speaker, OS Audio Stream, Native VAD/Wake)      |
+-------------------------------------------------------------------------+
                                    │ Audio Packets (PCM 16kHz / Opus)
                                    ▼
+-------------------------------------------------------------------------+
| L1: VOICE GATEWAY (Session Mgr, Streaming STT, Indic LID, TTS Engine)   |
+-------------------------------------------------------------------------+
                                    │ Transcripts / Events / Audio
                                    ▼
+-------------------------------------------------------------------------+
| L2: CONVERSATION & SESSION CONTEXT (State, Active Device, Short History) |
+-------------------------------------------------------------------------+
                                    │ User Query & Session Context
                                    ▼
+-------------------------------------------------------------------------+
| L3: INTENT & AGENT ROUTER                                               |
|  ├─ Fast Deterministic Match (Alarms, Timers, Media, System Status)     |
|  └─ Agentic State Handoff (LangGraph Workflows, Multi-Step Reasoning)    |
+-------------------------------------------------------------------------+
             │                                              │
  [Deterministic Path]                            [Agentic Path]
             │                                              │
             ▼                                              ▼
+-------------------------+               +-------------------------------+
| L5: TYPED TOOL RUNTIME  | <──────────── | L4: AGENT RUNTIME (LangGraph) |
+-------------------------+               +-------------------------------+
             │ Tool Invocation Plan
             ▼
+-------------------------------------------------------------------------+
| L6: POLICY & SECURITY LAYER (Risk Tiering, Auth, Human-in-the-Loop)     |
+-------------------------------------------------------------------------+
                                    │ Approved Tool Execution
                                    ▼
+-------------------------------------------------------------------------+
| L7: EXECUTION ENGINE (OS APIs, Shell Sandbox, Serena MCP, Web, Devices) |
+-------------------------------------------------------------------------+
                                    │ Raw Execution Output
                                    ▼
+-------------------------------------------------------------------------+
| L8: VERIFICATION LAYER (Evidence Gathering, Smoke Tests, State Probing) |
+-------------------------------------------------------------------------+
                                    │ Verified Result + Metrics
                                    ▼
+-------------------------------------------------------------------------+
| L9: LAYERED MEMORY & RAG (Working, Episodic, Semantic, Procedural)      |
+-------------------------------------------------------------------------+
                                    │ Response Text / Audio Stream
                                    ▼
+-------------------------------------------------------------------------+
| L10: OBSERVABILITY & TELEMETRY (OTel Traces, Latency, Token/Cost Meters) |
+-------------------------------------------------------------------------+
```

---

## 2. Layer Specifications

### L0 — Device Runtime
- **Role**: Native platform adapter running on Android, Windows, macOS, or Linux.
- **Components**:
  - Low-level microphone capture (16kHz 16-bit mono PCM).
  - Neural Wake Word detector (e.g., OpenWakeWord / customized Porcupine/MicroWakeWord) evaluating local audio buffers continuously without network roundtrips.
  - Silero VAD running locally to detect speech boundaries.
  - OS Permission and power-management hooks (Android Foreground Service, Windows Background Task).

### L1 — Voice Gateway
- **Role**: High-speed real-time audio pipeline and duplex communication hub.
- **Components**:
  - **Streaming STT Manager**: Pluggable provider interface (Faster-Whisper local, AI4Bharat IndicConformer for Hindi/Indic, Groq Whisper / Deepgram cloud fallback).
  - **Language Identification (LID)**: Instantaneous language tag detection (`en`, `hi`, `hi-Latn`, `hinglish`).
  - **TTS Synthesis Engine**: Low-latency streaming speech synthesizer with barge-in cancellation (EdgeTTS, Kokoro, IndicF5, ElevenLabs).

### L2 — Conversation & Session Context Layer
- **Role**: Maintains immediate conversational state across devices.
- **Components**:
  - Active device presence (phone vs. laptop vs. tablet).
  - Turn history buffer with strict token window budgeting.
  - Contextual entity resolution (e.g., resolving "it", "this project", "kal", "uska").

### L3 — Intent & Agent Router
- **Role**: Intelligent traffic cop determining the execution route in $< 50\text{ms}$.
- **Routing Rules**:
  1. If intent matches registered deterministic grammar / regex / small intent classifier (e.g. `set_alarm`, `stop_music`, `get_battery`) $\rightarrow$ Bypass LLM, execute directly.
  2. If intent requires factual lookup or single-step QA $\rightarrow$ Route to Fast Conversational LLM.
  3. If intent requires planning, multiple steps, code modification, or file operations $\rightarrow$ Dispatch to LangGraph Agent Runtime.

### L4 — Agent Runtime (LangGraph Engine)
- **Role**: Stateful, resilient, multi-step orchestration.
- **Components**:
  - State Graph with explicit nodes (`Plan`, `SelectTools`, `Execute`, `Critique`, `Verify`).
  - Checkpointer backed by PostgreSQL / SQLite for resumable execution across restarts.
  - Human-in-the-loop interruption nodes for sensitive operations.

### L5 — Typed Tool / Capability Layer
- **Role**: Strictly typed Pydantic / TypeScript contracts for all platform capabilities.
- **Categories**:
  - Core System Tools (File I/O, App Launch, Clipboard, Notification).
  - Assistant Tools (Alarms, Timers, Calendar, Contacts, Reminders).
  - Coding & Engineering Tools (Serena Semantic Code Engine, Git, Test Runners).
  - Web & Search Tools (Tavily/DuckDuckGo search, browser actions).
  - MCP Tool Bridges (Standardized external tool servers).

### L6 — Policy & Security Layer
- **Role**: Non-bypassable security gateway evaluating every tool call before invocation.
- **Components**:
  - Action Risk Classifier (`READ`, `REVERSIBLE_WRITE`, `EXTERNAL_COMMUNICATION`, `HIGH_IMPACT`).
  - Path traversal & shell injection sanitizers.
  - Prompt injection boundary isolating untrusted data from system instructions.
  - Interactive approval requester for high-impact actions.

### L7 — Execution Layer
- **Role**: Actual concrete driver execution across operating systems and sandboxes.

### L8 — Verification Layer
- **Role**: Self-healing and evidence generation.
- **Rule**: Never trust an unverified tool output. Checks HTTP status codes, process exit codes, filesystem diffs, or OS event receipts before reporting success.

### L9 — Memory & Knowledge Layer
- **Role**: Multi-tiered knowledge persistence (PostgreSQL for relational/session, `pgvector` for semantic embeddings, Redis for ephemeral caching).

### L10 — Observability Layer
- **Role**: Full-lifecycle tracing using OpenTelemetry standards, tracking TTFT (Time to First Token), STT latency, VAD latency, tool execution time, and token economics.

---

## 3. Multi-Device Orchestration & Satellite Topology

PIXEL deploys a **Central-Authority Controlled Satellite Topology** with asymmetric cryptography and mutual TLS (mTLS):

```
                   PIXEL CORE (Root CA & Policy Authority)
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
  Primary Desktop Node        Android Mobile            Satellite Nodes
(Desktop/Code Execution)   (Voice & Notifications)   (Room Mic/Speaker/Wake)
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    │
                    Canonical Device & Presence Registry
                                    │
                     Sliding-Window Wake Arbiter
                                    │
                     Context & Task Handoff Lease
```

### 3.1 PKI & mTLS Cryptographic Pairing
- **Root CA Authority (`PKIEngine`)**: Central PIXEL instance holds the self-signed Root CA and issues X.509/PIXEL PEM certificates with bounded validity and unique serials.
- **Explicit Pairing Flow**: Unpaired devices submit a `PairingRequest` with their public key. Core issues a 6-digit numeric PIN challenge with anti-brute-force rate limiting (maximum 3 attempts) and anti-replay nonce consumption upon authorization.
- **Revocation Ledger**: Compromised or decommissioned devices have their certificate serial and device ID blacklisted, immediately terminating mTLS handshakes and blocking re-pairing.

### 3.2 Canonical Device & Presence Registries
- **Device Registry (`DeviceRegistry`)**: Tracks hardware capabilities (`DESKTOP_CONTROL`, `ANDROID_CONTROL`, `CODE_EXECUTION`, `MICROPHONE`, `SPEAKER`, `DISPLAY`, `WAKE_WORD`) and cryptographic trust states.
- **Presence Manager (`PresenceManager`)**: Tracks real-time heartbeats with RTT latency, battery telemetry, and charging state. Devices failing to heartbeat within 30 seconds are automatically swept to `OFFLINE` status.

### 3.3 Multi-Satellite Wake-Event Arbitration (`WakeArbiter`)
- **Sliding-Window Deduplication**: Wake detections from multiple room microphones within $1500\text{ms}$ of an utterance are clustered into a single event group.
- **Deterministic Composite Scoring**: Candidates are ranked using:
  $$\text{Score} = (\text{Confidence} \times 50) + \text{SNR}_{\text{dB}} - (\text{Distance}_{\text{m}} \times 10) - (\text{RTT}_{\text{ms}} \times 0.1) + \text{InteractionOwnerBoost}$$
- **Single Active Session**: The highest-scoring candidate is elected active interaction owner; all other satellites receive suppression notifications to prevent dual-audio capture or double execution.

### 3.4 Cross-Device Context & Task Handoff (`HandoffManager`)
- **Scoped Context Migration**: Strips sensitive credentials, API keys, and bearer tokens (`_sanitize_context`) before replication between trusted, online nodes.
- **Optimistic Concurrency Leased Task Migration**: Emits cryptographically secure `concurrency_lease_token`s and increments task checkpoint versions, preventing stale updates or split-brain duplicate task runs while strictly preserving pending L6 `ApprovalCard` authorization bindings.

---

## 4. Custom Voice Cloning & Personalized Local Models (Phase 8)

PIXEL decouples biometric voice identity from language intelligence, preserving independent provider layers:

```
Voice Input (Mic / PCM)
    │
    ▼
STT Provider / VAD
    │
    ▼
Intent / Router Layer (LocalModelRouter)
    ├── <0.5ms Match ────────► Deterministic Intent Engine
    └── Complex Request ─────► Quantized Local LLM (4-bit GGUF/AWQ)
                                   │
                                   ├─ Tool Requests ─► L6 Policy Gate ─► Tool Registry
                                   ▼
                             Response Text
                                   │
                                   ▼
                       Personalized TTS Provider (Indian Prosody & Accent Conditioning)
                                   │
                                   ▼
                       Cloned Voice Output Stream
```

### 4.1 Speaker Embedding & Verification (`ECAPASpeakerEncoder`)
- **Multi-Band Spectral Extraction**: Extracts multi-band FFT spectral energies across 192 dimensions, normalized to the unit hypersphere with $L_2$-norm.
- **Biometric Cosine Similarity**: Computes cosine angle between reference profile embedding and incoming speech, using an experimentally calibrated threshold ($0.82$) with $0.05$ margin.
- **Signal Quality Gates**: Rejects degraded audio below minimum SNR ($12.0\text{dB}$) or insufficient valid speech duration ($<1.5\text{s}$).

### 4.2 Biometric Consent & Profile Management (`VoiceEnrollmentManager`)
- **Explicit Consent Tokens**: Enrollment strictly requires cryptographically structured consent tokens (`CONSENT_GRANTED_FOR_PERSONAL_VOICE_CLONING_V1`).
- **Zero Raw Audio Retention**: Raw WAV recordings are analyzed in-memory to generate speaker embeddings and then immediately destroyed. Only mathematical embeddings and anonymized acoustic parameters are stored.

### 4.3 Personalized Indian-Accent Synthesis (`PersonalizedTTSProvider`)
- **Acoustic Conditioning**: Synthesizes speech conditioned on mathematical `SpeakerProfile` vectors with customizable pitch scale, speaking rate, and breathiness.
- **Indian & Hinglish Prosody Modulation**: Native linguistic modulation for Indian English, Devanagari Hindi, and mixed-code Hinglish with natural transitions between Indic phonemes and English technical vocabulary.
- **Streaming Audio Chunks**: Generates incremental PCM audio chunks with cancellation and barge-in support.

### 4.4 4-Bit Quantized Local LLM Engine (`QuantizedLocalLLM`)
- **Model Family Support**: Optimized inference for Qwen2.5 (0.5B/1.5B/7B) and Llama-3.2 (1B/3B) architectures in 4-bit (AWQ/GGUF/BitsAndBytes) formats.
- **Structured Tool Call Parsing**: Intercepts native model tool calling formats and converts them into standardized PIXEL `ToolCall` contracts.
- **Zero Security Bypass**: Local LLMs operate under the same strict L6 `AgentPolicyGate` and L8 verification rules as remote models.

### 4.5 Hardware Resource Manager (`ModelResourceManager`)
- **VRAM / RAM Governors**: Tracks hardware resource consumption and enforces strict capacity limits (e.g. 8192MB ceiling).
- **FIFO Model Eviction**: Automatically unloads idle models when new models require memory allocation.
- **Cryptographic SHA-256 Integrity**: Validates model file checksums prior to loading to prevent malicious payload execution.

### 4.6 Hybrid Local-First Model Router (`LocalModelRouter`)
- **Preserved Fast-Path Intent**: Fast-path deterministic requests resolve in $<0.5\text{ms}$ with zero LLM token consumption.
- **Policy-Gated Remote Fallback**: Fallback to remote LLMs when local resources are exhausted requires explicit policy permission (`allow_remote_fallback=True`) to prevent silent exfiltration of private context.

---

## 5. Proactive & Autonomous Workflows (Phase 9)

PIXEL deploys a **Bounded Autonomy Execution Architecture** where proactive, scheduled, and long-running agents execute strictly within explicit goal boundaries, finite budgets, and continuous drift oversight:

```
Proactive Trigger (EventBus / Persistent Scheduler)
    │
    ▼
Task Specification (AutonomousTaskContract & Immutable GoalContract)
    │
    ▼
Concurrency Governor (TaskGovernor: Max 5 Slots, Starvation Protection)
    │
    ▼
Bounded Slice Execution (AutonomousWorkflowEngine: Max 5 Steps / Slice)
    │
    ├─ Persistent Budget Manager (Step / Tool / Duration / Token Caps)
    ├─ Goal Drift Detector (Semantic & Target Scope Defense)
    ├─ L6 Policy Gate (Approval Cards for High-Impact Actions)
    ├─ L8 Action Verifier (Execution Evidence Validation)
    ▼
Cryptographic Task Checkpoint (SHA-256 Hashed State)
    │
    ▼
Notification Dispatcher (TaskNotificationManager: Deduplicated User Alerts)
```

### 5.1 Event-Driven Bus & Deduplication (`EventBus`)
- **Predicate Filtering**: Subscriptions match event types using wildcard patterns (e.g. `device.*`, `system.metric_crossed`) and payload predicates.
- **Idempotency Window**: Deduplicates events within a sliding time window ($3600\text{s}$) using SHA-256 idempotency keys, preventing duplicate task dispatch from re-delivered events.

### 5.2 Persistent Task Scheduler (`AutonomousScheduler`)
- **SQLite Persistence**: Stores one-shot, interval, and cron-like task specifications and execution schedules.
- **Missed-Job Recovery Policies**: Automatically handles system downtime via deterministic policies (`EXECUTE_ONCE_NEXT_AVAILABLE`, `SKIP`, `RESCHEDULE`, `REQUIRE_APPROVAL`).
- **Mockable Clock Support**: Integrates simulated time providers for 100% deterministic testing without real wall-clock delays.

### 5.3 Explainable Goal Drift Detection (`GoalDriftDetector`)
- **Scope & Target Isolation**: Continuously verifies proposed targets (files, URLs, network hosts, databases) against `goal.allowed_targets`.
- **Prohibited Action Enforcement**: Blocks tool calls or plan steps matching prohibited actions/keywords (`delete`, `drop`, `force_push`).
- **Objective Divergence Guard**: Detects indirect prompt injection attempting to redefine the original task objective. Breaches trigger an immediate transition to `DRIFT_DETECTED` and pause execution.

### 5.4 Persistent Budget Accounting (`BudgetManager`)
- **Multi-Dimensional Resource Caps**: Hard ceilings for steps, tool calls, wall-clock duration, retries, and token consumption.
- **Crash-Resilient State**: Consumption metrics are persisted to SQLite at every step; restarts cannot reset or bypass budget limits.

### 5.5 Checkpointing & Safe Resume
- **Cryptographic Checkpoints**: State snapshots (`TaskCheckpoint`) compute SHA-256 checksums of active plans, completed steps, and budgets.
- **Tampering Defense**: Checkpoints with invalid checksums are rejected upon restoration.
- **Idempotent Cancellation**: Cancelled tasks permanently transition to `CANCELLED` and cannot be restarted.



