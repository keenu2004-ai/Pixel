# PIXEL — Observability, Metrics & Telemetry Specification
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## 1. Observability Architecture (OpenTelemetry Native)

PIXEL implements end-to-end tracing across all cognitive pipeline stages. Every user utterance generates a unified `TraceID` propagated through VAD $\rightarrow$ STT $\rightarrow$ Router $\rightarrow$ Agent Graph $\rightarrow$ Tool Execution $\rightarrow$ TTS $\rightarrow$ Playback.

```
[TraceID: a1b2c3d4...]
├── span: audio_capture_vad (35ms)
├── span: stt_streaming (180ms)
├── span: intent_routing (22ms)
├── span: langgraph_plan_node (320ms)
├── span: tool_serena_semantic_search (85ms)
├── span: tts_synthesis (140ms)
└── span: audio_stream_playback (210ms)
```

---

## 2. Key Metrics & SLIs

| Metric Name | Type | Target Threshold | Description |
| :--- | :--- | :--- | :--- |
| `pixel.voice.ttft_ms` | Histogram | $< 600\text{ms}$ (P95) | Time from speech end (VAD) to first generated audio chunk |
| `pixel.voice.wer` | Gauge | $< 10\%$ | Word error rate across test benchmark sentences |
| `pixel.agent.step_latency_ms` | Histogram | $< 1200\text{ms}$ (P95) | Latency per agent reasoning step |
| `pixel.tool.execution_duration_ms` | Histogram | $< 500\text{ms}$ (P95) | Time spent inside tool execution runtime |
| `pixel.token.total_consumed` | Counter | Monitored | Cumulative input/output token usage per session/day |
| `pixel.cost.usd_estimate` | Counter | Monitored | Real-time dollar burn rate tracking |
| `pixel.control_plane.api_latency_ms` | Histogram | $< 50\text{ms}$ (P95) | Control plane REST API response duration |
| `pixel.control_plane.ws_broadcast_ms` | Histogram | $< 5\text{ms}$ (P95) | Control plane WebSocket event broadcast dispatch |
| `pixel.control_plane.active_connections` | Gauge | Monitored | Number of authenticated operators connected via WebSocket |

---

## 3. Control Plane Observability & Audit Streams

The Control Plane exposes real-time administrative telemetry via `/ws/control-plane` and `/api/v1/audit/logs`:
- **Audit Logging**: Every security, task, scheduler, memory, and device administrative action emits a structured, timestamped audit record tagged with `actor_id`, `actor_role`, `action`, `resource_type`, `resource_id`, and `ip_address`.
- **Zero Raw Secret Telemetry**: Logs and telemetry streams are strictly scrubbed of tokens, passwords, private keys, and session cookies.
- **Client Backpressure Protection**: WebSocket broadcast buffers are bounded with drop-oldest drop queues to protect backend throughput against lagging clients.

---

## 4. Ecosystem & Extensibility Observability (Phase 11)

| Metric Name | Type | Target Threshold | Description |
| :--- | :--- | :--- | :--- |
| `pixel.ecosystem.plugin_dispatch_ms` | Histogram | $< 50\text{ms}$ (P95) | Subprocess sandbox launch and JSON-RPC roundtrip |
| `pixel.ecosystem.backup_duration_ms` | Histogram | $< 100\text{ms}$ (P95) | Client AES-GCM encryption and envelope generation |
| `pixel.ecosystem.webhook_dispatch_ms` | Histogram | $< 25\text{ms}$ (P95) | Webhook payload formatting, signing, and connector dispatch |
| `pixel.ecosystem.active_plugins` | Gauge | Monitored | Number of currently enabled third-party plugins |
| `pixel.ecosystem.active_connectors` | Gauge | Monitored | Number of active enterprise connectors |

---

## 5. Continuous Autonomous Evolution & Swarm Observability (Phase 12)

| Metric Name | Type | Target Threshold | Description |
| :--- | :--- | :--- | :--- |
| `pixel.swarm.leader_election_ms` | Histogram | $< 10\text{ms}$ (P95) | Dynamic leader election and lease acquisition latency |
| `pixel.swarm.consensus_latency_ms` | Histogram | $< 25\text{ms}$ (P95) | Multi-stage proposal voting, tallying, and L6 policy check |
| `pixel.mesh.sync_latency_ms` | Histogram | $< 15\text{ms}$ (P95) | Vector clock resolution and replication envelope merge |
| `pixel.evolution.dp_epsilon_consumed` | Gauge | Monitored | Cumulative differential privacy epsilon budget utilization |
| `pixel.evolution.active_swarms` | Gauge | Monitored | Number of active collaborative swarm sessions |
| `pixel.evolution.tripped_killswitches` | Gauge | Monitored | Number of active emergency shutdown trip switches |

### 5.1 Evolution Audit & Proposal Trails
- **Proposal Ledger (`pixel_proposals.db`)**: Records change proposal state machine transitions (`PROPOSED`, `ANALYZED`, `TESTING`, `VERIFIED`, `CANARY`, `APPROVED`, `PROMOTED`, `ROLLED_BACK`), diffs, canary percentages, and regression test codes.
- **Kill Switch Ledger (`pixel_killswitches.db`)**: Append-only log of emergency kill switch activation, actor IDs, timestamps, and justifications.

---

## 6. Real-World Execution & End-to-End Tracing Metrics (Phase 13)

| Metric Name | Type | Target Threshold | Description |
| :--- | :--- | :--- | :--- |
| `pixel.voice.total_voice_to_response_ms` | Histogram | $< 250\text{ms}$ (P95) | End-to-end voice perception to speech audio playback latency |
| `pixel.voice.wake_detection_latency_ms` | Histogram | $< 20\text{ms}$ (P95) | OpenWakeWord neural phrase detection latency |
| `pixel.voice.vad_latency_ms` | Histogram | $< 10\text{ms}$ (P95) | Silero / streaming VAD speech boundary detection latency |
| `pixel.voice.stt_latency_ms` | Histogram | $< 80\text{ms}$ (P95) | Faster-Whisper local CT2 speech transcription latency |
| `pixel.voice.tts_first_chunk_latency_ms` | Histogram | $< 50\text{ms}$ (P95) | Time to first synthesized audio chunk playback |
| `pixel.actions.android_dispatch_ms` | Histogram | $< 15\text{ms}$ (P95) | Android native intent & platform service dispatch latency |
| `pixel.mesh.handoff_latency_ms` | Histogram | $< 20\text{ms}$ (P95) | Cross-device context routing and response roundtrip latency |
| `pixel.tools.secret_redaction_count` | Counter | Monitored | Cumulative count of stripped credentials/secrets from tool outputs |



