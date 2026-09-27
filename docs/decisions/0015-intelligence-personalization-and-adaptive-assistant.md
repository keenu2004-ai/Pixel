# ADR 0015: Intelligence, Personalization & Adaptive Personal Assistant

- **Status**: Accepted
- **Date**: 2026-09-28
- **Context**: PIXEL Phases 0–14 established the robust real-world runtime foundation (voice streaming, OS/computer control, multi-device mesh, daily-driver hardening, L6 policy enforcement, and 0-leak soak stability). Phase 15 builds a dedicated intelligence and personalization layer that transforms PIXEL into a context-aware, adaptive personal AI operating layer while maintaining strict safety, truthfulness, privacy preservation, and reversibility guarantees.

## Decisions

1. **Dedicated Personalization Layer Architecture**:
   - `UserModelStore` & `UserModel` formalize user identity, preferences, active goals, routines, habits, and privacy boundaries.
   - Strict separation between `EXPLICIT_USER`, `USER_CONFIRMED`, `INFERRED`, and `OBSERVED` knowledge provenance.
   - Explicit user instructions always outrank inferred behaviors.

2. **Reversible Learning Loop & Conflict Resolution**:
   - `CorrectionLearner` recognizes user corrections ("No, I meant X", "I use Y now, not Z", "Be more concise") and applies updates via a managed loop: `OBSERVATION → HYPOTHESIS → CONFIDENCE → CONFIRMATION → UPDATE`.
   - Every learned personalization rule is reversible via an undo stack (`revert_preference`, `undo_last_correction`).
   - Newer explicit statements supersede older explicit statements.

3. **Habit Observation vs User-Governed Routines**:
   - Pattern detection is NOT permission: detected habits remain in `OBSERVED` status until the user explicitly authorizes them into active `UserRoutine` instances.
   - Proactive assistance is governed by an anti-annoyance budget (cooldowns, daily limits, acceptance/dismissal telemetry).

4. **Zero-Guessing Entity & Disambiguation Defense**:
   - `EntityResolver` maps personal vocabulary, projects, repositories, and contacts.
   - If multiple candidates match an ambiguous reference, PIXEL never guesses and instead raises an interactive clarification prompt.

5. **Minimal Relevant Context Assembly (<5ms)**:
   - `ContextEngine` ranks candidate items using multi-signal scoring (relevance, recency, confidence, explicitness).
   - Strict token budgets prevent prompt bloating and ensure ultra-low latency.

6. **Memory & Context Poisoning Defenses**:
   - `MemoryPoisoningDefense` strips adversarial prompt injections, jailbreaks, and privilege escalation attempts.
   - Memory content is treated strictly as reference data and wrapped in untrusted data envelopes, never as executable instructions or policy overrides.

7. **Cross-Device Context Mesh Sync**:
   - `CrossDeviceSyncManager` propagates signed deltas across trusted devices (Phone, Desktop, Server) and executes cascading Right-to-Forget deletions immediately.

## Consequences
- PIXEL acts as a genuinely personal, context-aware daily assistant.
- Absolute preservation of L6 Policy Gate, L8 Verification, and authorization boundaries.
- Zero false personalization and guaranteed user reversibility.
