# PIXEL — Retrieval-Augmented Generation (RAG) Architecture
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## 1. Pipeline Architecture

PIXEL's RAG system is distinct from internal agent memory. RAG indexes external documents, local codebases, manuals, and technical references.

```
[Raw Documents / Code / Web Pages]
                │
                ▼
1. INGESTION & NORMALIZATION (Markdown extraction, AST extraction, Code structure)
                │
                ▼
2. CHUNKING (Semantic-aware chunking, syntax-preserving AST blocks, 512-token max)
                │
                ▼
3. EMBEDDING & INDEXING (Text Embeddings + BM25 Full-Text Index in PostgreSQL/pgvector)
                │
                ▼
4. HYBRID RETRIEVAL (Vector Cosine Similarity + BM25 Keyword Search)
                │
                ▼
5. RERANKING (Cross-Encoder / Cohere / BGE Reranker)
                │
                ▼
6. CONTEXT SYNTHESIS (Strict citation attribution, prompt injection scrubbing)
```

---

## 2. Chunking & Indexing Standards

- **Code Files**: Tree-sitter AST-based chunking keeping entire function and class definitions intact.
- **Natural Language Documents**: Markdown header-aware chunking (H1/H2/H3 boundaries), with 50-token overlapping windows.
- **Hybrid Search**: Reciprocal Rank Fusion (RRF) combining dense vector search (`text-embedding-3-small` / local `bge-small-en-v1.5`) and sparse full-text search (`tsvector` in PostgreSQL).

---

## 3. Provenance & Citations

Every retrieved chunk injected into the LLM context must carry:
- `document_id`
- `source_uri` (file path or web URL)
- `chunk_hash`
- `retrieval_score`

The LLM is prompted to provide inline citations `[^1]` mapping to exact line numbers or source URLs.
