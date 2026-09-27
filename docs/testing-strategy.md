# PIXEL — Multi-Tier Testing Strategy
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## 1. Testing Pyramid & Verification Gates

PIXEL employs a strict 6-tier testing pyramid to enforce continuous stability across perception, reasoning, and execution layers:

```
          / \
         / E2E \          (Full voice loop, device actions)
        /-------\
       /  Voice  \        (WER, latency, Hinglish/Indic benchmarks)
      /-----------\
     /   Agent     \      (Tool selection, hallucination, retries)
    /---------------\
   /   Security      \    (Prompt injection, path traversal, SSRF)
  /-------------------\
 /     Integration     \  (DB, Redis, MCP tools, STT/TTS providers)
/-----------------------\
|         Unit          | (Entity extraction, risk policies, utils)
+-----------------------+
```

---

## 2. Testing Specifications by Layer

### 2.1 Unit Tests (`tests/unit/`)
- Pure, fast tests running in $< 5\text{seconds}$ without network dependencies.
- Coverage:
  - Intent router grammar and temporal parsing ("kal subah 7 baje" $\rightarrow$ timestamp).
  - Risk classification policy matrix.
  - Context window compaction and token estimators.
  - Data sanitization and PII redactor.

### 2.2 Integration Tests (`tests/integration/`)
- Verifies communication boundaries with SQLite/PostgreSQL, Redis, and mocked API providers.
- Coverage:
  - Memory persistence and `pgvector` semantic retrieval.
  - Serena MCP client communication.
  - TTS/STT streaming buffer handling.

### 2.3 Agent & Reasoning Tests (`tests/agent/`)
- Validates LangGraph state transitions and tool selection accuracy.
- Synthetic evals testing:
  - Zero tolerance for hallucinated tool names or unapproved arguments.
  - Graceful recovery when a tool returns a failure/timeout.
  - Correct invocation of human approval nodes for `HIGH_IMPACT` actions.

### 2.4 Voice & Indic Benchmark Tests (`tests/voice/`)
- Automated evaluation on curated bilingual audio test fixtures:
  - Speech-to-Text Word Error Rate (WER) on Hindi, Hinglish, and regional accents.
  - Time-to-First-Audio (TTFA) latency benchmarking.
  - Barge-in cancellation responsiveness during active TTS playback.

### 2.5 Security & Injection Tests (`tests/security/`)
- Adversarial test harness executing:
  - Direct and indirect prompt injection attempts.
  - Sandboxed command injection and path escape attempts.
  - SSRF probe queries against cloud metadata and private IP ranges.
