# PIXEL — Personal AI Voice & Agent Operating Layer

<div align="center">

[![CI Pipeline](https://github.com/keenu2004-ai/Pixel/actions/workflows/ci.yml/badge.svg)](https://github.com/keenu2004-ai/Pixel/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Architecture: Layered L0-L10](https://img.shields.io/badge/Architecture-Layered%20L0--L10-emerald.svg)](docs/architecture.md)

*An ambient, multilingual, voice-first personal AI operating layer engineered for natural Indic/English speech, deterministic speed, policy-governed tool execution, and stateful agentic problem-solving.*

</div>

---

## 🌟 Vision & Core Philosophy

**PIXEL** is not a chatbot wrapper or a toy demo. It is a long-term personal AI operating platform designed to:
- **Perceive** mixed-language natural speech across English, Hindi, Hinglish, Haryanvi, and regional Indic patterns with sub-800ms response targets.
- **Differentiate** between instant deterministic actions (alarms, apps, media) and deep, multi-step agentic workflows (codebase debugging, multi-hop research, computer control).
- **Enforce** non-bypassable risk policies (`READ`, `REVERSIBLE_WRITE`, `EXTERNAL_COMMUNICATION`, `HIGH_IMPACT`) before any tool execution.
- **Maintain** layered, private memory (Working, Episodic, Semantic, Procedural) with full user data sovereignty.
- **Operate** seamlessly across Desktop (PC), Mobile (Android), Web Dashboard, and Server Nodes.

---

## 🏗️ 10-Layer Cognitive Architecture

```
[L0: Device Runtime] (Audio Stream, Silero VAD, Wake Detection: "Hey Pixel", "Oye Pixel")
        │
        ▼ Audio Stream
[L1: Voice Gateway] (Streaming STT, Indic LID, Low-Latency Bilingual TTS)
        │
        ▼ Transcripts & Events
[L2: Conversation Context] (Active Device, Session Context, Window Compaction)
        │
        ▼
[L3: Intent & Agent Router]
   ├── [Fast Deterministic Path] (<300ms: Alarms, Timers, Media, System Status)
   └── [Agentic State Path] (LangGraph: Multi-Step Research, Coding, Computer Control)
        │
        ▼ Tool Invocations
[L6: Policy & Security Layer] (Risk Evaluation, Injection Scrubbing, Human Approval)
        │
        ▼ Approved Tool Calls
[L7: Execution Engine] (Native OS APIs, Serena MCP Semantic Code Engine, Sandboxed Shell)
        │
        ▼ Raw Output
[L8: Verification Layer] (Evidence Gathering, Smoke Tests, State Probing)
        │
        ▼ Verified Outcomes
[L9: Layered Memory & RAG] (Working, Episodic, Semantic, Procedural Stores)
        │
        ▼ Response Stream
[L10: Observability Layer] (OpenTelemetry Tracing, TTFT Latency, Token/Cost Metrics)
```

---

## 📚 Source of Truth Documentation

All engineering contracts and design specifications are rigorously documented under [`docs/`](docs/):

- **[Product Requirements Document (PRD)](docs/product-requirements.md)**: Vision, use cases, functional specifications, NFRs, and acceptance criteria.
- **[Design System & Voice States](docs/design-system.md)**: 11 distinct operational states, visual halos, and typography tokens.
- **[System Architecture](docs/architecture.md)**: Full L0–L10 layer breakdown and event-driven data flow.
- **[Agent Catalog](docs/agents.md)**: Specialized agent boundaries, state graphs, and failure policies.
- **[Tool Registry](docs/tool-registry.md)**: Typed Pydantic schemas, timeouts, and 4-tier risk classification.
- **[Memory Architecture](docs/memory-architecture.md)**: 5-tier memory models, extraction agents, and privacy policies.
- **[RAG Architecture](docs/rag-architecture.md)**: AST-based chunking, hybrid search, and source provenance.
- **[Security Architecture](docs/security-architecture.md)**: Threat modeling, prompt injection defense, and sandbox boundaries.
- **[Observability](docs/observability.md)**: OpenTelemetry metrics, SLIs, and latency budgets.
- **[Testing Strategy](docs/testing-strategy.md)**: 6-tier pyramid (Unit, Integration, Agent, Voice/Indic, Security, E2E).
- **[Performance & Economics](docs/performance.md)**: Sub-800ms deterministic budgets and token burn-rate models.
- **[Phased Roadmap](docs/roadmap.md)**: 10-phase milestone plan from Phase 0 to Phase 9.
- **[Engineering Rules](docs/engineering-rules.md)**: Karpathy-style simplicity, Generate-Critique-Refine-Verify loop.
- **[Architecture Decision Records (ADRs)](docs/decisions/)**:
  - `ADR-001`: Language & Runtime Selection (Python + TypeScript + Kotlin)
  - `ADR-002`: Voice Pipeline & Indic Language Architecture
  - `ADR-003`: Deterministic Fast-Path vs. LangGraph State Machine
  - `ADR-004`: Storage Layer (SQLite / PostgreSQL + pgvector)
  - `ADR-005`: Computer Use, Serena Semantic Engine & Sandboxing

---

## 🚀 Phased Implementation Roadmap

- [x] **Phase 0: Foundation & Engineering Harness** (Contracts, packaging, test harness, CI)
- [x] **Phase 1: Core Voice Perception & Synthesis Loop** (Silero VAD, Wake detection, Streaming STT/TTS)
- [x] **Phase 2: Deterministic Intent Engine & OS Capabilities** (Alarms, Timers, Reminders, Hinglish Parser)
- [x] **Phase 3: Layered Memory & RAG Knowledge Engine** (Episodic/Semantic memory, AST chunking, Vector retrieval)
- [x] **Phase 4: LangGraph Agent Runtime & Tool Policy Engine** (State graphs, non-bypassable L6 policy, L8 verification)
- [x] **Phase 5: Computer Control & Serena Semantic Coding** (AST code exploration, patch verification, isolated test runner)
- [x] **Phase 6: Android System Assistant** (VoiceInteractionService, background daemon, role manager)
- [x] **Phase 7: Multi-Device Satellites & Distributed Context** (mTLS pairing, multi-satellite wake arbitration, context migration)
- [x] **Phase 8: Voice Cloning & Local Quantized Models** (Speaker embeddings, 4-bit quantized local LLMs, VRAM governor)
- [x] **Phase 9: Proactive & Autonomous Workflows** (Event-driven monitors, persistent scheduler, goal drift defense)
- [x] **Phase 10: Production Hardening & Full-Stack Control Plane** (Unified web dashboard, RBAC, WebSocket streaming, Docker containerization)
- [x] **Phase 11: Community Ecosystem & Extensibility Hub** (Sandboxed plugin engine, skill marketplace, AST security vetting, zero-knowledge backups, enterprise connectors)
- [x] **Phase 12: Continuous Autonomous Evolution & Self-Healing Swarms** (Multi-agent swarms, self-healing diagnostic loops, distributed edge memory mesh, differentially private model evolution)
- [x] **Phase 13: Real-World Assistant Integration & End-to-End Execution** (Real microphone/voice streaming with barge-in, native Android action adapters, sandboxed filesystem/terminal/browser tools, multi-device handoffs, E2E missions)
- [x] **Phase 14: Production Reality, Daily-Driver Hardening & Personal Assistant Readiness** (24-hour soak stability, zero-loss crash recovery, Doze & lifecycle hardening, multi-turn ambiguity resolution, transactional schema rollback, objective daily-driver scorecard)
- [ ] **Phase 15: Edge AI Swarm Deployment & Autonomous Fleet Operations** (Cross-platform binary packaging, peer-to-peer gossip protocol, fleet operations)

---

## 🛠️ Quickstart (Development & Production Setup)

### Prerequisites
- Python 3.11 or higher
- Git
- Docker & Docker Compose (optional, for production containerization)

### Local Development Installation
```bash
# Clone repository
git clone https://github.com/keenu2004-ai/Pixel.git
cd Pixel

# Set up Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# Install project dependencies in editable mode
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env

# Run full verification suite (375 tests)
pytest
mypy packages services
ruff check .
```

### Launching the Production Control Plane & Runtime
```bash
# Option 1: Native Python runtime
python -m uvicorn services.control_plane.server:app --host 0.0.0.0 --port 8000

# Option 2: Production Containerization via Docker Compose
docker compose -f infra/docker/docker-compose.yml up --build -d
```
Access the Control Plane Web Dashboard at `http://localhost:8000`.

Default administrative credentials:
- **Admin**: `admin` / `admin_pixel_2026`
- **Operator**: `operator` / `operator_pixel_2026`
- **Viewer**: `viewer` / `viewer_pixel_2026`

---

## 🔒 Security & Contribution Philosophy

PIXEL operates on a **Zero Blind Trust** policy:
1. **No secrets in git**: All credentials must reside in local `.env` (gitignored).
2. **Four-Pillar Execution**: Every feature must execute through `CLEAR CONTEXT → EXECUTION PROTOCOL → INTERNAL CRITIC → EXIT CONDITION`.
3. **Simplicity First**: Reject speculative abstractions and unnecessary dependencies.

