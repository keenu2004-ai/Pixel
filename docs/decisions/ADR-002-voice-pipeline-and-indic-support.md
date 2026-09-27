# ADR-002: Voice Pipeline, Pluggable Providers & Indic Language Architecture
**Status:** Accepted  
**Date:** 2026-09-27  

## Context
PIXEL must support seamless English, Hindi, Hinglish, Haryanvi, and mixed-language speech with low latency (<800ms) and natural Indian accents. No single proprietary cloud provider provides zero-latency, private, and culturally accurate Indian speech synthesis and recognition simultaneously.

## Decision
1. **Perception**: Silero VAD v5 + OpenWakeWord / Porcupine as lightweight local perception layer.
2. **STT (Speech-to-Text)**:
   - *Primary Local/Hybrid*: Faster-Whisper + AI4Bharat IndicConformer for native Hindi/Hinglish phonetics.
   - *Cloud Fallback*: Groq Whisper / Deepgram Nova-2 for ultra-fast cloud streaming.
3. **TTS (Text-to-Speech)**:
   - *Primary Local*: Kokoro v0.19 / IndicF5 for natural multilingual prosody.
   - *Cloud Fallback*: EdgeTTS (free, high quality) / ElevenLabs / Cartesia.
4. **Architecture**: Pluggable provider interface (`BaseSTTProvider`, `BaseTTSProvider`, `BaseVADProvider`) with automatic fallback on timeout or error.

## Consequences
- Clean separation allows swapping models as new state-of-the-art open models release without refactoring the agent runtime.
