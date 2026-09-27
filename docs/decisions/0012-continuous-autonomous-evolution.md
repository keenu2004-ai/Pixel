# ADR-0012: Continuous Autonomous Evolution, Self-Healing Swarms & Governed Model Lifecycle

## Status
**ACCEPTED** (Phase 12 Architectural Baseline)

## Context
PIXEL operates across heterogeneous edge topologies (PC, Android, Satellites, Server). As the system scales, it requires capabilities to:
1. Orchestrate multi-agent collaborative swarms with deterministic consensus and dynamic leader election.
2. Continually profile runtime telemetry, formulate explainable root-cause hypotheses, and safely self-heal transient degradations.
3. Synchronize distributed memory across edge devices without centralized server plaintext access while resolving conflicts deterministically and guaranteeing tombstone deletion propagation.
4. Adapt and distill personal local models with rigorous differential privacy accounting, interaction lineage tracking, and strict non-regression evaluation.
5. Provide non-bypassable governance controls, immutable safety boundaries, and emergency kill switches.

## Architectural Decision

### 1. Swarm Coordination & Hierarchical Consensus
- **Bounded Swarm Coordinator**: `SwarmCoordinator` allocates finite budgets and tracks agent lifecycle states (`INITIALIZING`, `IDLE`, `ASSIGNED`, `EXECUTING`, `VOTING`, `DEGRADED`, `UNRESPONSIVE`, `FAILED`, `QUARANTINED`, `TERMINATED`).
- **Dynamic Leader Election**: `LeaderElection` establishes epoch-based leases with sliding-window heartbeat renewals and deterministic tie-breaking (trust level $\rightarrow$ role priority $\rightarrow$ lexicographical ID).
- **Subordinated Consensus**: Consensus is strictly an orchestration mechanism. Reaching swarm consensus does not bypass security; all approved proposals must flow through the canonical L6 `AgentPolicyGate` and L8 `ActionVerifier`.

### 2. Observation-First Self-Profiling & Diagnostic Engine
- **Telemetry Buffers**: `RuntimeSelfProfiler` captures rolling metrics in bounded ring buffers.
- **Diagnostic Hypothesis Engine**: `DiagnosticEngine` maps observed threshold breaches to explainable `RootCauseHypothesis` records and candidate `RemediationProposal` objects.
- **Strict Remediation Allowlist**: Safe classes (`RESTART_WORKER`, `RENEW_LEASE`, `CLEAR_BOUNDED_CACHE`, `RETRY_TRANSIENT`, `SWITCH_MODEL_REPLICA`, `FAILOVER_DEVICE`) are permitted to execute under policy; structural code/policy changes strictly require operator approval.

### 3. Change Proposal Lifecycle & Regression Test Generation
- **Separation of Proposal vs. Application**: Proposals follow a strict state machine (`PROPOSED` $\rightarrow$ `ANALYZED` $\rightarrow$ `TESTING` $\rightarrow$ `VERIFIED` $\rightarrow$ `CANARY` $\rightarrow$ `APPROVED` $\rightarrow$ `PROMOTED` / `ROLLED_BACK`).
- **AST Safety Guard on Generated Tests**: `RegressionTestGenerator` parses candidate regression pytest code into ASTs, ensuring the presence of assertions and rejecting forbidden primitives (`os.system`, `subprocess`, `sys.exit`, or attempts to mock/bypass L6/L8).

### 4. Decentralized Memory Mesh
- **Vector Clock Causality**: `MemoryConflictResolver` evaluates vector clocks to determine dominance or concurrent divergence.
- **Tombstone Deletion Guarantee**: Memory deletions generate tombstones that propagate across the mesh and take precedence over stale state.
- **Conflict Isolation**: Concurrent unresolvable modifications are quarantined in `ConflictRecord` ledgers rather than silently overwritten.

### 5. Privacy-Preserving Model Evolution
- **Lineage & Right-to-be-Forgotten**: `DatasetLineageTracker` binds interaction samples to cryptographic consent tokens; user consent revocation immediately disqualifies affected training samples.
- **Differential Privacy**: `DifferentialPrivacyAccountant` enforces hard $(\epsilon, \delta)$ ceilings and injects calibrated Gaussian/Laplace noise during training.
- **Model Evaluation & Safe Promotion**: `ModelSafetyEvaluator` audits benchmark accuracy, hallucination scores ($\le 5\%$), prompt injection resistance ($\ge 95\%$), and 100% policy compliance before candidate models can enter canary or active promotion.

### 6. Emergency Kill Switches & Evolution Governor
- **Persistent Kill Switches**: `KillSwitchSystem` stores immutable trip switches in SQLite across 6 domains (`ALL_SWARMS`, `AUTONOMOUS_REMEDIATION`, `MODEL_PROMOTION`, `CODE_PROMOTION`, `MEMORY_REPLICATION`, `TRAINING_PIPELINE`).
- **Non-Bypassable Invariance**: Once tripped, autonomous agents cannot self-reset kill switches; reset strictly requires authenticated administrator authority.

## Consequences
- **Positive**: Enables robust, self-diagnosing, self-healing autonomy without sacrificing safety, predictability, or user privacy.
- **Trade-offs**: Autonomous agents cannot self-modify safety-critical code or policies; manual administrator approval is intentionally required for structural patches.
