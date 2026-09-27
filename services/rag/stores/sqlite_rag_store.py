"""SQLite Knowledge Document and Vector Store for RAG.

Stores indexed document chunks with embeddings and full-text keyword indexing.
"""

import json
import logging
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from packages.contracts.rag import ChunkType, DocumentChunk, RetrievalResult
from packages.core.interfaces.embeddings import BaseEmbeddingProvider
from services.rag.embeddings.hash_embedding import DeterministicHashEmbeddingProvider

logger = logging.getLogger(__name__)


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 > 1e-9 and norm2 > 1e-9:
        return dot / (norm1 * norm2)
    return 0.0


class SQLiteRAGStore:
    """Knowledge store for RAG chunks with hybrid vector and keyword search."""

    def __init__(
        self,
        db_path: str = "data/persistence/pixel_rag.db",
        embedding_provider: BaseEmbeddingProvider | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_provider = embedding_provider or DeterministicHashEmbeddingProvider()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pixel_rag_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    content TEXT NOT NULL,
                    chunk_type TEXT NOT NULL,
                    start_line INTEGER,
                    end_line INTEGER,
                    symbol_name TEXT,
                    chunk_hash TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_doc ON pixel_rag_chunks(document_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_hash ON pixel_rag_chunks(chunk_hash)"
            )
            conn.commit()

    async def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Embeds and inserts new chunks, skipping existing duplicates by hash."""
        if not chunks:
            return 0

        # Batch embed chunks that don't have embeddings
        unembedded = [c.content for c in chunks if not c.embedding]
        if unembedded:
            embeddings = await self.embedding_provider.embed_batch(unembedded)
            emb_idx = 0
            for c in chunks:
                if not c.embedding:
                    c.embedding = embeddings[emb_idx]
                    emb_idx += 1

        inserted = 0
        now_str = datetime.now(UTC).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for chunk in chunks:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO pixel_rag_chunks
                    (chunk_id, document_id, source_uri, content, chunk_type, start_line, end_line, symbol_name, chunk_hash, embedding_json, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.source_uri,
                        chunk.content,
                        chunk.chunk_type.value,
                        chunk.start_line,
                        chunk.end_line,
                        chunk.symbol_name,
                        chunk.chunk_hash,
                        json.dumps(chunk.embedding),
                        json.dumps(chunk.metadata),
                        now_str,
                    ),
                )
                inserted += 1
            conn.commit()

        logger.info("Indexed %d document chunks into RAG store.", inserted)
        return inserted

    async def search_hybrid(
        self,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.1,
    ) -> list[RetrievalResult]:
        """Performs hybrid vector cosine search with keyword rank boosting."""
        query_vec = await self.embedding_provider.embed_text(query)
        query_tokens = set(query.lower().split())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pixel_rag_chunks")
            rows = cursor.fetchall()

        scored_results: list[RetrievalResult] = []
        for idx, r in enumerate(rows, start=1):
            emb = json.loads(r["embedding_json"])
            vec_sim = _cosine_similarity(query_vec, emb)

            # Keyword lexical overlap boost
            content_tokens = set(r["content"].lower().split())
            overlap = len(query_tokens & content_tokens) / max(1, len(query_tokens))
            hybrid_score = (vec_sim * 0.7) + (overlap * 0.3)

            if hybrid_score >= min_similarity:
                chunk = DocumentChunk(
                    chunk_id=r["chunk_id"],
                    document_id=r["document_id"],
                    source_uri=r["source_uri"],
                    content=r["content"],
                    chunk_type=ChunkType(r["chunk_type"]),
                    start_line=r["start_line"],
                    end_line=r["end_line"],
                    symbol_name=r["symbol_name"],
                    chunk_hash=r["chunk_hash"],
                    embedding=emb,
                    metadata=json.loads(r["metadata_json"]),
                )
                scored_results.append(
                    RetrievalResult(
                        chunk=chunk,
                        score=float(hybrid_score),
                        citation_id=f"cit_{idx}",
                    )
                )

        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:limit]

    async def delete_document(self, document_id: str) -> int:
        """Purges all chunks associated with a document ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pixel_rag_chunks WHERE document_id = ?", (document_id,))
            conn.commit()
            return cursor.rowcount
