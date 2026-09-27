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
