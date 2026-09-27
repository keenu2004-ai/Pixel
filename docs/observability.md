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
