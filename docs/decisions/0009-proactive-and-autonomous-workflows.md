# ADR 0009: Proactive & Autonomous Workflows with Bounded Autonomy and Goal Drift Control

## Status
Accepted

## Context
PIXEL requires autonomous execution capabilities for proactive background monitors, recurring health/maintenance schedules, event-driven integrations, and long-running multi-step agents.
Unconstrained agent loops (`while true: let agent decide`) introduce catastrophic failure modes:
1. Runaway execution and resource/budget exhaustion.
2. Silent goal drift where the model diverges from the user-approved objective.
3. Tool escalation and privilege expansion.
4. Duplicate task runs caused by re-delivered events or un-idempotent scheduler triggers.
5. Inability to safely pause, checkpoint, inspect, or cancel autonomous tasks.
6. Silent bypass of L6 security policy and L8 verification.

## Decision
We implement a **Bounded Autonomy Execution Architecture** governed by immutable goal contracts, persistent execution budgets, explainable goal drift detection, event deduplication, and non-bypassable policy enforcement:

1. **Autonomous Task Contract (`AutonomousTaskContract`)**:
   - Explicitly defines immutable `GoalContract` (objective, success criteria, constraints, allowed targets, prohibited actions).
   - Strict `ExecutionBudget` (max steps, max tool calls, max wall-clock duration, max retries, max tokens).
   - Strict `ToolAllowlist` (explicit permitted tools; LLM cannot self-authorize additional tools).
   - Explicit `DriftPolicy` and `NotificationPolicy`.

2. **Event Bus & Normalization (`EventBus`)**:
   - In-memory/persistent event bus with typed events (`AutonomousEvent`).
   - Idempotent deduplication by `event_id` and `idempotency_key`.
   - Typed predicate filtering (`EventFilter`) to route events to matching task subscriptions.

3. **Persistent Scheduler (`AutonomousScheduler`)**:
   - Persists one-shot and recurring/cron jobs to SQLite.
   - Deterministic missed-job recovery policies (`EXECUTE_ONCE_NEXT_AVAILABLE`, `SKIP`, `RESCHEDULE`, `REQUIRE_APPROVAL`).
   - Mockable clock provider to enable 100% deterministic time simulation in CI.

4. **Goal Drift Detection Engine (`GoalDriftDetector`)**:
   - Segment-level semantic and structural comparison of proposed plans, tool calls, and targets against the canonical `GoalContract`.
   - Evaluates: objective divergence, unauthorized external targets, prohibited tool categories, unexpected mutations.
   - Explains drift reason and triggers automatic execution pause and user escalation (`DRIFT_DETECTED`).

5. **Persistent Budget Accounting & Checkpointing (`BudgetManager`, `Checkpointer`)**:
   - Cumulative budget consumption is persisted at every step and checkpoint boundary.
   - Process crashes and restarts cannot reset execution limits.

6. **Concurrency & Resource Governor (`TaskGovernor`)**:
   - Limits concurrent running tasks (e.g. max 5) and concurrent LLM inferences to prevent starvation and memory exhaustion.
   - FIFO/fair scheduling with bounded time-slice execution segments.

7. **Zero Security Bypass**:
   - All tool invocations must route through `AgentPolicyGate` (L6) and `ActionVerifier` (L8).
   - Approvals for high-risk actions are time-bounded and cryptographically bound to specific tasks and arguments.

## Consequences
- Autonomous tasks operate safely within hard mathematical and policy boundaries.
- System state is 100% recoverable across process restarts with zero duplicate execution.
- Goal drift is detected and halted before dangerous unconstrained operations occur.
