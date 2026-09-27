# ADR 0008: Custom Voice Cloning & Personalized Local Model Architecture

## Context
PIXEL requires local voice personalization (few-shot speaker embeddings, Indian-accent adaptation, Hindi/English code-switching) and local intelligence (quantized 4-bit local LLMs from Qwen and Llama families) while maintaining sub-millisecond deterministic routing, non-bypassable L6 policy gates, biometric voice privacy, and resource isolation.

## Decisions

1. **Independent Provider Separation**:
   - Voice identity (Speaker Encoder, Voice Cloner, TTS) is strictly decoupled from language intelligence (Local LLM, Agent Runtime, Intent Router).
   - Voice cloning models (e.g. Kokoro-Style, F5-TTS, or ECAPA-TDNN speaker encoder) and local LLMs (Qwen2.5 / Llama-3.2 4-bit quantized) adhere to typed base interfaces.

2. **Authorized Voice Enrollment & Biometric Privacy**:
   - Voice cloning requires explicit user consent (`ConsentDeclaration`) and signed authorization.
   - Enrolled voice profiles store mathematical speaker embedding vectors (e.g. 192-d or 512-d normalized floats) with SHA-256 integrity signatures, not raw audio recordings.
   - Voice samples are validated for SNR ($>15\text{dB}$), duration ($3\text{s}-30\text{s}$), and speech clarity before enrollment.

3. **Indian Accent & Code-Switching (Hinglish)**:
   - Voice synthesis engine dynamically conditions on language tags (`en`, `hi`, `hi-Latn`, `hinglish`) and Indian English phoneme sets.
   - Preserves natural prosody and pronunciation for bilingual conversational utterances.

4. **Quantized 4-Bit Local LLM Engine**:
   - Supports 4-bit quantized local model formats (`Q4_K_M`, `INT4`, GGUF/ONNX) with explicit lifecycle states (`UNLOADED`, `LOADING`, `READY`, `INFERENCING`, `UNLOADING`, `ERROR`).
   - Local LLM routes tool calls strictly through the canonical `ToolRegistry` and enforces non-bypassable L6 `AgentPolicyGate` and L8 `ActionVerifier`.

5. **Model Resource Management & Scheduling**:
   - Central `ModelResourceManager` monitors memory/compute utilization, prevents memory exhaustion, and schedules model loads with safety limits.
   - Preserves the deterministic fast-path ($< 0.5\text{ms}$) with zero LLM/TTS overhead.

## Consequences
- 100% offline, privacy-first voice synthesis and agentic reasoning on local desktop/mobile hardware.
- Safe, authorized few-shot voice personalization without leaking biometrics.
- Modular provider architecture allowing seamless swapping of speaker encoders, TTS backends, and local LLM backends.
