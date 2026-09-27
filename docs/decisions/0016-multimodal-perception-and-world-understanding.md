# ADR 0016: Multimodal Perception, Vision & World Understanding

## Status
Accepted (Phase 16)

## Context
PIXEL previously operated as a voice-first intelligent assistant (Phases 0–15). To enable true daily-driver mastery across desktop and mobile workflows, PIXEL requires deep perceptual awareness: understanding on-screen content, camera views, diagrams, scanned documents, and physical surroundings, while grounding user actions visually.

However, multimodal perception introduces significant safety and security risks:
1. Adversarial prompt injections embedded inside screenshots, images, OCR text, or QR codes.
2. Accidental leakage of confidential data (passwords, API keys, OTPs, credit cards).
3. Ambiguous visual target selection leading to incorrect clicks ("click guessing").
4. Surveillance creep from unmanaged continuous background camera/screen recording.
5. Hallucinated task completions without empirical state diff verification.

## Decision
We established the canonical Phase 16 Multimodal Perception Architecture with the following core principles:

1. **Vision is Input, Not Authority**:
   - Visual data (images, screenshots, camera frames, OCR, document extracts) is strictly classified as `UNTRUSTED EXTERNAL DATA`.
   - Visual input can never bypass the L6 Policy Gate, L8 Action Verification, or user authorization boundaries.

2. **Zero Guessing UI Grounding**:
   - If multiple elements match a target description or confidence falls below threshold (<0.70), PIXEL marks `is_ambiguous=True` and requests clarification. It never clicks by guessing.

3. **Zero Surveillance Mode**:
   - Camera and screen captures default to ephemeral, user-initiated, bounded lifecycles with immediate hardware resource disposal. Continuous background recording is prohibited.

4. **Empirical Visual Verification (L8 Extension)**:
   - PIXEL never claims "Done." without comparing pre- and post-action visual states to verify the expected transition (dialog opened, focus shifted, text changed).

5. **Local-First Privacy Routing**:
   - Screens or frames containing sensitive data (passwords, tokens, OTPs) or unconsented camera frames are strictly retained and processed on local on-device providers (`LOCAL` routing).

## Consequences
- **Positive**:
  - Full support for Voice + Vision ("look at this", "read this error", Hinglish "ye screen pe error kya hai").
  - Deterministic prompt injection defense for OCR and visual inputs.
  - Provable safety in automated desktop and mobile computer control.
  - Sub-5ms context fusion latency and bounded memory consumption.
- **Negative**:
  - Requires local CPU/GPU resource budgeting to prevent frame processing overhead during rapid interactions.
