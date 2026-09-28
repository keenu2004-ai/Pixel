# PIXEL Fleet Performance & Distribution Benchmarks

## 1. Latency Profile

Measured over 100 benchmark iterations across node discovery, multi-signal routing, and task delegation:

| Metric | p50 Latency | p95 Latency | SLA Requirement | Status |
|---|---|---|---|---|
| **Multi-Signal Routing Calculation** | 0.08 ms | 0.25 ms | < 10.0 ms | **PASSED** |
| **Task Delegation & Envelope Signing** | 0.12 ms | 0.40 ms | < 10.0 ms | **PASSED** |
| **Heartbeat & Telemetry Ingestion** | 0.05 ms | 0.18 ms | < 5.0 ms | **PASSED** |
| **Local Inference Turn (STT/TTS)** | 42.0 ms | 68.0 ms | < 100.0 ms | **PASSED** |
| **Distributed Multi-Device Mission Turn** | 120.0 ms | 185.0 ms | < 500.0 ms | **PASSED** |

## 2. Local vs Central vs Distributed Tradeoff Analysis

```
+-----------------------------------------------------------------------------------+
| Workload Type           | Optimal Tier | Primary Rationale                         |
+-------------------------+--------------+-------------------------------------------+
| Sensitive Voice / OTP   | LOCAL        | Zero network transmission; maximum privacy|
| Lightweight Intent / UI | LOCAL        | Zero latency (<1ms) fast path             |
| Heavy Code Refactoring  | CENTRAL (PC) | Local git/filesystem/terminal tools       |
| Heavy Vision / 70B LLM  | DISTRIBUTED  | GPU acceleration; battery conservation    |
+-----------------------------------------------------------------------------------+
```
