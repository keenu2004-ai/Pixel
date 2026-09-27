"""PostgreSQL / pgvector Storage Schema for PIXEL Memory and RAG Subsystems."""

SCHEMA_DDL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Semantic Facts Table
CREATE TABLE IF NOT EXISTS pixel_facts (
    fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'general',
    key VARCHAR(256) NOT NULL,
    value_json JSONB NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    provenance TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    superseded_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_facts_user_key ON pixel_facts(user_id, key) WHERE is_active = TRUE;

-- 2. Episodic Memory Table
CREATE TABLE IF NOT EXISTS pixel_episodes (
    episode_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    summary TEXT NOT NULL,
    interaction_type VARCHAR(32) NOT NULL DEFAULT 'conversation',
    embedding vector(384),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_episodes_user ON pixel_episodes(user_id);
CREATE INDEX IF NOT EXISTS idx_episodes_vector ON pixel_episodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 3. RAG Knowledge Document Chunks Table
CREATE TABLE IF NOT EXISTS pixel_rag_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR(128) NOT NULL,
    source_uri TEXT NOT NULL,
    content TEXT NOT NULL,
    chunk_type VARCHAR(32) NOT NULL DEFAULT 'TEXT_PARAGRAPH',
    start_line INTEGER,
    end_line INTEGER,
    symbol_name VARCHAR(256),
    chunk_hash VARCHAR(64) NOT NULL,
    embedding vector(384),
    tsv_content tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc ON pixel_rag_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_tsv ON pixel_rag_chunks USING gin (tsv_content);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_vector ON pixel_rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""
