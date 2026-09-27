# ADR-004: Unified Persistence: SQLite (Local) / PostgreSQL + pgvector (Server) & Redis
**Status:** Accepted  
**Date:** 2026-09-27  

## Context
PIXEL requires persistent storage for relational entities (users, devices, sessions, tasks, policy logs) and vector embeddings for semantic memory and RAG, as well as high-throughput ephemeral caching for streaming audio and rate-limiting.

## Decision
1. **Local Standalone Mode**: SQLite + `sqlite-vec` / ChromaDB for zero-dependency desktop standalone operation.
2. **Server / Cloud Node Mode**: PostgreSQL 16+ with `pgvector` for unified relational + vector queries in a single ACID store.
3. **Cache & Ephemeral Streaming**: Redis / DragonFly for active session token buckets, audio buffer streams, and lock management.

## Consequences
- Prevents database sprawl (no separate vector DB clusters like Pinecone needed when PostgreSQL + `pgvector` suffices).
