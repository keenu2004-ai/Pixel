# PIXEL — Agent Architecture & Specialization Specification
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## 1. Principles of Agent Specialization

1. **No Monolithic Super-Agent**: Large monolithic prompts fail on edge cases, hallucinate tool parameters, and inflate token consumption.
2. **Distinct Scopes & State Graphs**: Every agent has a clear mandate, a strictly bounded toolset, input/output schemas, and an explicit failure policy.
3. **Internal Critic & Verification**: All agentic modifications must pass through an automated evaluation/verification cycle before completion.

---

## 2. Core Agent Catalog

### 2.1 Conversation & Intent Router (`RouterAgent`)
- **Objective**: Parse user intent, language, and context to determine the fastest, safest execution pathway.
- **Input**: Raw speech transcript, session history, active device metadata.
- **Output**: Routed Intent Packet (`intent_type`, `params`, `confidence`, `target_agent`).
- **Tools**: Fast entity extractors, temporal normalizer.
- **Bypass**: Deterministic intents (e.g. `alarm.create`, `volume.set`) bypass all LLM agent loops.

### 2.2 Coding & Engineering Agent (`CodingAgent`)
- **Objective**: Inspect repositories, debug errors, formulate minimal diffs, execute tests, and verify fixes.
- **Tool Suite**:
  - Serena MCP Semantic Code Tools (symbol search, find references, inspect AST).
  - Shell / Test Runner Sandbox (`pytest`, `npm test`, `cargo test`).
  - Git Diff & Patch Generator.
- **Execution Loop**:
  $$\text{Analyze Error} \longrightarrow \text{Retrieve Symbols} \longrightarrow \text{Reproduce via Test} \longrightarrow \text{Minimal Patch} \longrightarrow \text{Run Tests} \longrightarrow \text{Verify Clean Diff}$$
- **Safety Policy**: Diff size $> 50$ lines or touching production config triggers `ActionApprovalCard`.

### 2.3 Computer Control Agent (`ComputerAgent`)
- **Objective**: Automate desktop tasks (application management, window focus, structured file operations).
- **Tool Suite**: `open_app`, `focus_window`, `read_clipboard`, `write_clipboard`, `capture_active_window`.
- **Constraint**: No arbitrary OCR-driven raw coordinate clicking unless accessibility tree APIs are unavailable. All shell execution must be allowlisted.

### 2.4 Research & Knowledge Agent (`ResearchAgent`)
- **Objective**: Multi-hop web and document research, citation synthesis, and knowledge summarization.
- **Tool Suite**: `search_web` (Tavily/DDG), `read_url`, `rag_retrieve`, `rerank_documents`.
- **Constraint**: External untrusted content is strictly wrapped in sandbox tags and scrubbed of prompt-injection payloads.

### 2.5 Memory Management Agent (`MemoryAgent`)
- **Objective**: Asynchronously extract persistent facts, user preferences, and procedural learnings from completed sessions.
- **Trigger**: Post-session background worker.
- **Tools**: `store_semantic_memory`, `update_user_preference`, `delete_obsolete_memory`.
- **Constraint**: Never logs passwords, API keys, or raw confidential chat transcripts without user opt-in.

### 2.6 Reviewer & Critic Agent (`CriticAgent`)
- **Objective**: Independent audit of generated code, plans, or critical tool arguments before final commit.
- **Evaluation Criteria**:
  - Did the plan satisfy the original prompt?
  - Are there regressions, dead code, or unnecessary abstractions?
  - Are all security boundaries and type signatures preserved?
