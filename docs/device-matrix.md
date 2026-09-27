# PIXEL Physical & Runtime Device Matrix

## Supported Device Hardware & Runtime Roles

| Device Category | Target Platform | Typical Hardware Specs | Supported Capabilities | Verification Level |
| :--- | :--- | :--- | :--- | :--- |
| **Mobile Assistant (Primary)** | Android 14+ (ARM64) | 8-12 GB RAM, 8-Core CPU, Dual Mic | Wake word, VAD, STT, TTS, Native Intents (Calls, SMS, Alarms, Timers, Media, Calendar, App Launch), Handoff, Doze Adaptation | LEVEL 4 (Physical Device) |
| **Primary Workstation (PC)** | Windows 11 / Linux (x86_64) | 16-64 GB RAM, Multi-Core, Hardware Mic/Speaker | Sandboxed Terminal, Safe Filesystem, Controlled Browser, Git Automation, LangGraph Reasoning, Local LLM Inference | LEVEL 3 (Local Real Runtime) |
| **Central Hub / Server** | Linux (Ubuntu 24.04 LTS) | Multi-Core Cloud/Edge Server | Multi-Device Coordinator, Memory Mesh Sync, Model Evolution & Governance, Differential Privacy Accounting | LEVEL 3 (Local Runtime / Cloud) |
| **Satellite Audio Node** | Linux / ESP32 / Android TV | 512 MB - 2 GB RAM, Far-field Mic Array | Wake detection, Bounded PCM streaming, Audio playback, Wake arbitration candidate | LEVEL 2 / LEVEL 3 |

## Safety & Invariant Guarantees Across Matrix
1. **Zero Raw Audio Persistence:** Raw PCM audio is streamed through async memory buffers and immediately drained upon VAD silence / processing.
2. **Deterministic Wake Arbitration:** When multiple devices hear the wake word, the central hub elects a single winner via `MultiDeviceRuntime.arbitrate_wake_word()` based on confidence and latency score, suppressing satellite echoes.
3. **Graceful Degradation:** When disconnected from the mesh, each device node seamlessly switches to local deterministic capabilities.
