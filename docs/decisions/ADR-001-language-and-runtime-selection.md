# ADR-001: Language & Runtime Architecture Selection
**Status:** Accepted  
**Date:** 2026-09-27  

## Context
PIXEL requires high-performance audio streaming, low-latency machine learning inference (VAD, STT, TTS, Indic models), OS-level integration (Android, Windows, Linux), and an extensible agent/tool ecosystem.

## Decision
1. **Core Service & Agent Runtime**: **Python 3.11+ (FastAPI + AsyncIO + Pydantic v2)**.
   - *Rationale*: Python is the primary ecosystem for modern voice ML libraries (Silero, Faster-Whisper, PyTorch, AI4Bharat IndicConformer, Kokoro, LangGraph).
2. **Web & Desktop UI**: **TypeScript + React / Vite + Tailwind CSS + WebSockets**.
   - *Rationale*: Type-safe, component-driven reactive interface for real-time waveforms and execution timelines.
3. **Android Assistant Module**: **Kotlin + Android SDK (VoiceInteractionService)**.
   - *Rationale*: Direct native binding to Android OS assistant role and Alarm/Calendar APIs.

## Alternatives Considered
- *Pure Rust/Go*: High performance but inadequate native library ecosystem for Indic ML speech models and rapid agent prototyping.
- *Pure Node.js*: Lacks robust native bindings for specialized Hindi/Indic speech models without heavy C++ wrapping.

## Consequences
- Requires clean inter-process communication (WebSockets / gRPC / JSON-RPC) between the native Android/Desktop frontends and the Python voice/agent runtime.
