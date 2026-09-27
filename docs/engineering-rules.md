# PIXEL — Engineering Discipline & Execution Rules
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## 1. The Karpathy Engineering Principles

1. **Think Before Coding**:
   - Explicitly identify assumptions and ambiguities.
   - Surface tradeoffs before writing code. Never silently invent requirements.
2. **Simplicity First**:
   - Build the smallest architecture that solves the concrete problem.
   - Reject speculative abstractions and framework layers that do not provide measurable value.
3. **Surgical Changes**:
   - Modify only what is strictly required. Never perform drive-by refactoring of unrelated code.
   - Clean up orphaned code, imports, and variables created by any change.
4. **Goal-Driven Execution**:
   - Every task must possess clear, measurable success criteria and verifiable tests.

---

## 2. The Four-Pillar Execution Loop

Every non-trivial engineering action must follow:

```
[CLEAR CONTEXT] ──> [EXECUTION PROTOCOL] ──> [INTERNAL CRITIC] ──> [EXIT CONDITION]
```

### Pillar 1: CLEAR CONTEXT
Define:
- Objective
- Current system state
- Relevant files and dependencies
- Explicit constraints & assumptions
- Non-goals

### Pillar 2: EXECUTION PROTOCOL
Define:
- Exactly what changes and why
- What must remain unchanged
- Tests to add or run
- Step-by-step verification commands

### Pillar 3: INTERNAL CRITIC
Perform an adversarial self-review:
- *Did I solve the requested problem?*
- *Did I introduce unnecessary complexity or speculative abstractions?*
- *Did I duplicate existing code or database tables?*
- *Did I break existing behavior or type safety?*
- *Is there a simpler, cleaner way to do this?*
- *What would fail in production or under high load?*

### Pillar 4: EXIT CONDITION
Do not declare completion until:
- All unit, integration, or benchmark tests pass.
- Typecheck (`mypy`/`pyright`) passes with 0 errors.
- Linter (`ruff`/`eslint`) passes with 0 warnings.
- No dead code, orphaned imports, or duplicate logic remains.

---

## 3. Codebase Hygiene & Dead Code Policy

1. **Continuous Static Analysis**:
   - Run dead code analyzers (`vulture`, `unused-deps`, `ruff check --select F401,F841`) before committing any milestone.
2. **Never Blindly Delete Ambiguous Code**:
   - Trace references using AST, Serena symbol search, or grep before pruning legacy code.
   - Document any architectural deprecation explicitly.
