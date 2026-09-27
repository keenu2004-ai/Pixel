# ADR 0013: Real-World Assistant Integration & End-to-End Execution

## Status
Accepted

## Date
2026-09-28

## Context
Phases 0–12 established PIXEL's multi-layered foundation: low-latency voice streaming, deterministic and autonomous agent routing, immutable L6 policy and L8 verification gates, episodic/semantic memory with differential privacy, autonomous swarm consensus, and emergency kill switches.

Phase 13 moves PIXEL from an architectural platform into a real, end-to-end usable personal assistant operating across physical Android devices, desktop/terminal runtimes, browser automation, and multi-device meshes.

## Decisions

1. **Physical & Simulated Microphone Runtime**:
   - Implemented `MicrophoneRuntime` with bounded async FIFO buffering (`AudioStreamBuffer`), zero raw audio persistence, and non-blocking PCM 16kHz mono capture.

2. **Full Streaming Voice & Barge-In Loop**:
   - Built `StreamingVoiceLoop` executing `MIC -> WAKE -> VAD -> STT -> ROUTER -> PLAN -> TOOL -> L6 -> EXECUTION -> L8 -> MEMORY -> TTS -> SPEAKER`.
   - Enabled instant interruption (`trigger_barge_in`) which terminates in-flight TTS generation and cancels pending downstream steps when the user begins speaking.

3. **Real Android Native Action Adapters**:
   - Built `AndroidActionAdapter` and Kotlin `AndroidActionHandler` covering Phone Calls, SMS, Alarms, Timers, Media, Calendar, and App Launching.
   - Enforced contact resolution and ambiguity detection (refuses to dial blindly when ambiguous matches exist).
   - Enforced immutable L6 Policy Gate evaluation on all native device actions.

4. **Safe Filesystem, Controlled Terminal & Sandboxed Browser Tools**:
   - `SafeFilesystemTool`: Strict workspace root containment preventing `../` path traversal escapes, file size limits, and `HIGH_IMPACT` deletion gates.
   - `TerminalTool`: Automatic regex-based secret scrubbing (API keys, JWTs, tokens), 30s timeout, dangerous pattern blocking (`rm -rf /`, `mkfs`).
   - `ControlledBrowserTool`: Sandboxed navigation, domain allowlist enforcement, and automatic prompt injection sanitization on untrusted web content.

5. **Multi-Device Mesh & Context Handoff**:
   - Implemented `MultiDeviceRuntime` supporting Phone, Desktop, Server, and Satellite nodes.
   - Distributed wake arbitration electing the lowest-latency/highest-confidence responder.
   - Seamless cross-device context transfer (Phone hears -> Server plans -> Desktop executes -> Phone speaks).
   - Graceful offline degradation and network recovery reconciliation preventing duplicate action execution.

6. **Canonical ToolRegistry Integration**:
   - Registered all real-world tools into `ToolRegistry` with typed schemas, risk classifications (`READ`, `REVERSIBLE_WRITE`, `HIGH_IMPACT`), and L6/L8 enforcement.

## Consequences
- PIXEL executes real actions on Android, Windows/Desktop, terminal, and web environments with full safety guarantees.
- Immutable safety invariants (L6 Policy, L8 Verification, auth, crypto, and kill switches) remain non-bypassable.
