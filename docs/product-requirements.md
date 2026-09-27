# PIXEL — Product Requirements Document (PRD)
**Status:** Approved Source of Truth  
**Version:** 1.0.0  
**Last Updated:** 2026-09-27  

---

## 1. Executive Vision & Core Philosophy

**PIXEL** is a personal AI operating layer and voice-first agent platform. It is not an ephemeral chat widget, a brittle script collection, or an unconstrained LLM wrapper. PIXEL provides ambient, cross-platform intelligence that can:
1. **Perceive** natural speech across multiple languages (English, Hindi, Hinglish, Haryanvi, and regional Indic speech).
2. **Understand & Disambiguate** user intent with temporal, contextual, and spatial awareness.
3. **Route & Plan** requests deterministically for fixed tasks (alarms, apps, media) or agentically via state graphs for complex, multi-step tasks (research, coding, computer control).
4. **Execute Tools Safely** through a strictly enforced policy, risk classification, and sandbox boundary.
5. **Verify Outcomes** via evidence-based feedback loops rather than blind assertion.
6. **Maintain Layered Memory** (working, episodic, semantic, procedural) while honoring strict user privacy and consent policies.
7. **Operate Everywhere** across Desktop (PC), Mobile (Android), Web Dashboard, and Server Nodes.

### The Cognitive Loop
$$\text{Perception} \longrightarrow \text{Understanding} \longrightarrow \text{Planning} \longrightarrow \text{Tool Selection} \longrightarrow \text{Execution} \longrightarrow \text{Verification} \longrightarrow \text{Memory Retention} \longrightarrow \text{Response}$$

---

## 2. Target Users & Core Scenarios

### 2.1 Target Personas
1. **The Power Developer & Knowledge Worker**: Needs hands-free control of development workflows ("PIXEL, inspect the auth error in my active repo, run tests, and explain the failure"), file operations, calendar orchestration, and technical research.
2. **The Bilingual / Multilingual Indian User**: Speaks in mixed Hindi-English (Hinglish/Khadi Boli) naturally ("*Hey Pixel, kal subah 7 baje ka alarm laga dena aur Spotify pe lofi chala dena*"), expecting zero friction with code-switching or regional accents.
3. **The Multi-Device Orchestrator**: Seamlessly moves from Desktop to Android phone, expecting shared task state, device-aware execution (e.g., ringing an alarm on the phone vs. launching a build on the PC), and unified memory.

### 2.2 Canonical Interaction Scenarios

#### Scenario A: Mixed-Language Ambient Deterministic Command
- **User**: *"Oye Pixel, kal subah 7 baje mujhe utha dena."*
- **Perception**: Wake phrase detected locally $\rightarrow$ Audio captured $\rightarrow$ VAD signals end-of-speech $\rightarrow$ Multilingual STT transcribes $\rightarrow$ Language identified as `hi-Latn / Hinglish`.
- **Understanding**: Intent: `alarm.create`. Temporal resolution: `kal subah 7 baje` $\rightarrow$ `current_date + 1 day @ 07:00:00 local_tz`.
- **Policy Check**: Action Class: `REVERSIBLE_WRITE`. Privilege: Auto-approved for authenticated user.
- **Execution**: Android Alarm Intent / OS Clock API triggered.
- **Verification**: OS confirms alarm ID registered.
- **Response**: Multilingual TTS speaks: *"Kal subah 7 baje ka alarm set kar diya hai."*

#### Scenario B: Agentic Coding & Computer Control
- **User**: *"Pixel, meri laptop pe jo project chal raha hai usme authentication ka error dekh aur fix kar."*
- **Perception**: Wake / Audio $\rightarrow$ Intent classified as `agent.code.investigate_and_fix`.
- **Routing**: Handed off to LangGraph-based `Coding Agent` with Serena semantic tooling.
- **Planning**:
  1. Locate active project directory from session state.
  2. Semantically retrieve symbols associated with `auth`, `login`, `session`, `JWT`.
  3. Execute test suite to reproduce failure.
  4. Formulate minimal diff to patch the failure.
  5. Run unit & integration tests to verify fix.
  6. Request user confirmation before applying permanent filesystem/git write if diff exceeds low-risk threshold.
- **Response**: Structured report explaining root cause, exact lines modified, and passing test results.

---

## 3. Capability Map & Functional Requirements

### 3.1 Voice & Perception (P0)
- **Wake Word Engine**: Lightweight, offline, low-power wake word detection supporting flexible triggers: *"Hey Pixel"*, *"O Pixel"*, *"Are Pixel"*, *"Oye Pixel"*, *"Pixel sun"*.
- **Voice Activity Detection (VAD)**: Energy and neural VAD (e.g., Silero) capable of sub-30ms frame processing and robust noise suppression.
- **Speech-to-Text (STT)**:
  - Streaming transcription with interim and final hypotheses.
  - Native support for English, Hindi (Devanagari & Latin/Hinglish), Haryanvi, and code-switching without language thrashing.
  - Hybrid local (Faster-Whisper / IndicConformer) and cloud fallback.
- **Text-to-Speech (TTS)**:
  - Low-latency streaming synthesis (<250ms time-to-first-audio chunk).
  - Indian English & Hindi natural intonation (IndicF5 / Kokoro / EdgeTTS / Cloud fallback).
  - Interruptibility / barge-in support (stopping playback immediately upon user speech detection).

### 3.2 Intent Resolution & Layered Routing (P0)
- **Deterministic vs. Agentic Split**:
  - Deterministic fast path for: Alarms, timers, reminders, app launches, media controls, system status. (Bypasses LLM planning graphs; latency target <400ms).
  - Agentic state path for: Multi-step research, codebase debugging, computer control, cross-service orchestrations.
- **Temporal & Spatial Normalization**: Robust parser for relative time expressions in Hindi/English ("kal", "parso", "agla somwar", "in 20 mins").

### 3.3 Platform & Device Runtime (P1)
- **Android Integration**:
  - `VoiceInteractionService` architecture for system-level assistant integration.
  - Role manager integration for default digital assistant.
  - Background service persistence with strict battery optimization handling.
  - OS capability integration via intents & content providers: Alarms (`AlarmManager`), Calendar, Contacts, Telephony/SMS (with explicit OS permissions).
- **Desktop (Windows/macOS/Linux)**:
  - Application lifecycle management (launch, focus, kill).
  - Safe terminal execution sandbox with allowlisted commands.
  - Semantic filesystem navigation and Serena MCP code engine integration.
- **Web & Dashboard Control Plane**:
  - Real-time conversation viewer, task monitor, memory browser, tool permission manager, audit logs, and security dashboard.

### 3.4 Tool & Capability Ecosystem (P0/P1)
- **Typing & Contracts**: Every tool is defined by strict Pydantic/TypeScript JSON schemas for inputs and outputs.
- **Risk Classification System**:
  - `READ`: Low risk (e.g., read calendar, search docs, check weather).
  - `REVERSIBLE_WRITE`: Moderate risk (e.g., set alarm, create draft note).
  - `EXTERNAL_COMMUNICATION`: Sensitive (e.g., send SMS, post message, place call). Requires contextual confirmation.
  - `HIGH_IMPACT`: Destructive / privileged (e.g., delete files, wipe database, modify security tokens). Mandatory explicit user confirmation.

### 3.5 Memory & Context (P1)
- **Working Memory**: Active session and multi-turn scratchpad with strict token pruning.
- **Episodic Memory**: Vector + relational record of notable past events, interactions, and explicit outcomes.
- **Semantic Memory**: Persistent user facts, preferences, and personal knowledge base with clear user inspection and edit UI.
- **Procedural Memory**: Reusable learned procedures and user-specific tool sequences.
- **Privacy Controls**: Zero automatic persistence of sensitive credentials or unapproved conversations. Explicit "Forget" and "Export" APIs.

---

## 4. Non-Functional Requirements (NFRs)

| Dimension | Requirement / Target | Measurement Method |
| :--- | :--- | :--- |
| **End-to-End Voice Latency** | $\le 800\text{ms}$ (Deterministic), $\le 1500\text{ms}$ (Streaming LLM first token) | Telemetry timestamp diff from VAD speech end to first audio packet output |
| **Wake Word False Positives** | $< 1$ per 24 hours ambient noise | Continuous 24h background audio test dataset |
| **Hindi/Hinglish WER** | $< 12\%$ Word Error Rate on conversational mixed speech | Curated Indic speech benchmark suite |
| **Availability & Uptime** | $99.9\%$ for local core; graceful degradation on network loss | Heartbeat ping & synthetic health checks |
| **Security & Isolation** | 0 unauthenticated tool executions; strict sandboxed execution | Automated prompt injection & path traversal penetration suites |
| **Resource Footprint** | Local background daemon: $< 300\text{MB}$ RAM idle, $< 5\%$ CPU idle | Process monitor benchmarks on Windows/Android |

---

## 5. Non-Goals (Explicit Out-of-Scope)

1. **Not an Unbounded AGI Claim**: PIXEL does not claim autonomous consciousness or unbounded self-rewriting agents. All autonomy is capability-scoped and policy-bounded.
2. **Not a Raw Prompt Dump**: No monolithic 20,000-token superprompts with raw shell tool access.
3. **No Blind Web Automation / Scraping without Permissions**: Browser automation is strictly constrained to authorized user sessions with credential sandboxing.
4. **No Premature Microservice Bloat**: Core services run as a clean, cohesive modular service layer before any distributed splitting.
