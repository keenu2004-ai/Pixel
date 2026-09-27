# ADR-003: Deterministic Fast-Path vs. LangGraph Agent State Machine
**Status:** Accepted  
**Date:** 2026-09-27  

## Context
Voice assistants often fail in production by forcing every trivial command ("turn off music", "set alarm for 7am") through large, non-deterministic LLM agent loops. This causes high latency, hallucinated parameters, and wasted cost. Conversely, complex tasks (code analysis, multi-hop research) require stateful planning and retries.

## Decision
1. **Deterministic Fast-Path Router**:
   - Commands with known grammar/intents (alarms, timers, media, volume, app launches) are routed directly to native deterministic handlers.
   - Bypasses LLM generation entirely.
   - Latency target: $< 300\text{ms}$.
2. **LangGraph State Machine for Complex Tasks**:
   - Multi-step tasks, code debugging, and open-ended workflows are dispatched to LangGraph state graphs with explicit checkpointing, retries, and human-in-the-loop approval nodes.

## Consequences
- Eliminates latency and token waste on 80% of daily assistant commands while retaining deep agentic power for knowledge work.
