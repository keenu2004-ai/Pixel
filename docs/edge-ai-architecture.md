# PIXEL Edge AI Architecture

## 1. Architectural Overview

PIXEL transforms heterogeneous edge hardware into a unified, privacy-first Edge AI computing layer. Edge devices contribute local perception (microphone, camera, screen) and edge inference (Whisper STT, Kokoro TTS, CLIP vision, small quantized LLMs) while delegating heavier reasoning and tool operations according to resource constraints.

```
+-------------------------------------------------------------------------+
|                        PIXEL CENTRAL AUTHORITY                          |
|  Identity PKI | L6 Policy Gate | L8 Verifier | Model & Memory Authority  |
+-------------------------------------------------------------------------+
                                    |
          +-------------------------+-------------------------+
          |                         |                         |
+-------------------+     +-------------------+     +-------------------+
|   MOBILE NODE     |     |   DESKTOP NODE    |     |    GPU SERVER     |
| (Pixel / Android) |     |  (Primary Core)   |     |   (Edge Cloud)    |
| - Local STT / TTS |     | - Browser / OS    |     | - Heavy LLM (70B) |
| - Camera / Screen |     | - Code / Terminal |     | - Heavy Vision    |
| - Low-Power NPU   |     | - Git Automation  |     | - Embeddings/RAG  |
+-------------------+     +-------------------+     +-------------------+
```

## 2. Multi-Signal Routing Pipeline

When a user initiates an action or multimodal query, the `FleetRoutingEngine` evaluates placement along 6 dimensions:
1. **Capability Matching**: Does the candidate node have the required software/hardware capability?
2. **Privacy Classification**:
   - `HIGHLY_SENSITIVE`: Forced to `LOCAL` tier on originating node.
   - `SENSITIVE` / `PERSONAL`: Restricted to trusted devices with TLS/PKI encryption.
   - `LOW_SENSITIVITY` / `PUBLIC`: Flexible offload to least-loaded compute node.
3. **Battery Conservation**: Battery < 20% triggers automatic offload of compute-heavy tasks.
4. **Thermal Constraints**: Thermally throttled nodes (`WARM`, `THROTTLED`) avoid heavy tensor processing.
5. **Network Condition**: Offline nodes automatically degrade to local-only functions (timers, voice memos).
6. **Latency Budget**: Compares network transfer RTT against local execution time.

## 3. Provider-Independent Inference Runtime

Edge runtimes support three deployment tiers:
- **LOCAL**: In-process ONNX Runtime, NPU, or quantized llama.cpp model on edge device.
- **REMOTE**: High-throughput inference server hosted on local GPU workstation or LAN server.
- **HYBRID**: Local feature extraction (e.g. cropped screen/audio frames) with remote reasoning and local speech synthesis.
