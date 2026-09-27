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

### 4.1 Ecosystem Audit Trails
- **Plugin Ledger (`pixel_plugins.db`)**: Records state transitions (`INSTALLED`, `ENABLED`, `DISABLED`, `REVOKED`, `QUARANTINED`), permission grants, and emergency revocation events.
- **Backup Registry (`pixel_backups.db`)**: Records encrypted envelope revisions, scopes, checksums, and restoration timestamps.
- **Connector Registry (`pixel_connectors.db`)**: Records connector registrations, outbound webhook deliveries, status codes, and SSRF violation rejections.

