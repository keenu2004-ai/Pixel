# PIXEL Personalization & Adaptive Intelligence Architecture

## 1. Overview
The Personalization Layer in PIXEL sits directly on top of the hierarchical Memory Engine and feeds into the Context Engine, Agent Runtime, Intent Engine, and Voice Gateway.

```
                  ┌────────────────────────┐
                  │      Conversation      │
                  └───────────┬────────────┘
                              │
                  ┌───────────▼────────────┐
                  │     Context Engine     │
                  └───────────┬────────────┘
                ┌─────────────┴─────────────┐
                │                           │
     ┌──────────▼──────────┐     ┌──────────▼──────────┐
     │    Memory Engine    │     │      User Model     │
     └──────────┬──────────┘     └──────────┬──────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                  ┌───────────▼────────────┐
                  │ Personalization Engine │
                  └───────────┬────────────┘
                ┌─────────────┼─────────────┐
                │             │             │
     ┌──────────▼──┐   ┌──────▼──────┐   ┌──▼──────────┐
     │ Preferences │   │   Habits    │   │    Goals    │
     └──────────┬──┘   └──────┬──────┘   └──┬──────────┘
                └─────────────┼─────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
     ┌──────────▼──┐   ┌──────▼──────┐   ┌──▼──────────┐
     │ Agent Engine│   │  L6 Policy  │   │ Voice/Tools │
     └─────────────┘   └─────────────┘   └─────────────┘
```

## 2. Core Pillars & Design Invariants

### 2.1 Explicit vs Inferred Memory Hierarchy
Every retained fact possesses typed provenance:
- `EXPLICIT_USER`: Stated directly by the user (Confidence 1.0).
- `USER_CONFIRMED`: Inferred hypothesis explicitly approved by user (Confidence 0.95–1.0).
- `INFERRED`: Derived statistically from interaction patterns (Confidence 0.5–0.94).
- `OBSERVED`: One-time behavioral observation (Confidence < 0.5).

**Invariant**: Inferred knowledge *never* overrides explicit user instructions.

### 2.2 Reversible Learning Loop
Learning occurs through a bounded state machine:
`OBSERVATION → HYPOTHESIS → CONFIDENCE → OPTIONAL CONFIRMATION → PERSONALIZATION UPDATE → FUTURE USE`
Every learned rule is reversible and can be undone via `undo_last_correction()` or `revert_preference()`.

### 2.3 Habit Detection vs User-Governed Routines
- Detection is NOT permission: habits remain in `OBSERVED` status.
- Once the user explicitly approves a pattern, it transitions into an active `UserRoutine`.

### 2.4 Minimal Relevant Context Assembly (<5ms)
- Multi-signal ranking: relevance, recency, confidence, explicitness, task relationship.
- Hard token budget (<800 tokens) to prevent prompt bloat.

### 2.5 Security & Poisoning Defense
- Memory content is strictly wrapped in untrusted data envelopes.
- Rejects jailbreaks, prompt injection, and attempts to override system safety policy.

### 2.6 Cross-Device Context Mesh
- Synchronizes user preferences, active goals, and entities across Phone, Desktop, and Server nodes.
- Enforces cryptographic revocation checks.
