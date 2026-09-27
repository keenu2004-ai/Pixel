# ADR 0014: Production Reality, Daily-Driver Hardening & Personal Assistant Readiness

- **Status**: Accepted
- **Date**: 2026-09-28
- **Context**: PIXEL Phases 0–13 established the full real-world execution stack (`MIC → WAKE → VAD → STT → ROUTER → PLAN → TOOL → L6 → EXECUTION → L8 → MEMORY → TTS → SPEAKER`), alongside native Android, OS, browser, terminal, and multi-device capabilities. Phase 14 hardens this foundation into a robust, daily-driver personal AI assistant that reliably operates under real-world constraints (process deaths, network drops, background Doze, ambiguous speech, long-run soak).

## Decision
1. **Verification Evidence Hierarchy (Levels 0–5)**:
   - Level 0: Static / Unit tests
   - Level 1: Synthetic simulation
   - Level 2: Emulator
   - Level 3: Local Real Runtime
   - Level 4: Physical Connected Device
   - Level 5: Continuous Multi-Hour / Daily-Driver Soak
   Every capability must report its true verified level without false claims.

2. **Zero-Loss Crash Recovery & Lifecycle Hardener**:
   - `AssistantLifecycleHardener` handles `APP_BACKGROUND`, `APP_FOREGROUND`, `DOZE_MODE_ENTER`, `DOZE_MODE_EXIT`, `PERMISSION_REVOKED`, and `PROCESS_KILLED`.
   - In-flight tasks automatically checkpoint and rehydrate upon reboot or process restart.

3. **Ambiguity Defense & Conversational Context**:
   - `ConversationalContextManager` prohibits guessing when multiple entities exist (e.g. multiple "Rahul" contacts), instead prompting an explicit interactive clarification card.
   - Handles conversational directives ("cancel that", "do that again", "forget what I just said").

4. **Transactional Migration & Rollback Engine**:
   - `MigrationEngine` creates pre-migration cryptographic state snapshots and executes automatic rollbacks on any schema failure.

5. **Continuous Soak & Non-Subjective Scorecard**:
   - `ContinuousSoakRunner` and `ReadinessEvaluator` compute empirical metrics for wake, STT, TTS, action success, battery drain, memory growth, and security resistance.

## Consequences
- PIXEL achieves robust daily-driver stability with 0 memory leaks across 24h cycles.
- Absolute preservation of all L6 Policy Gate, L8 Verification, and privacy boundaries.
- No false "Done" reports: all actions require verified post-execution state evidence.
