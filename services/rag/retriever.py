"""Hybrid RAG Knowledge Retrieval Engine.

Coordinates vector similarity, lexical search, and context assembly.
"""

from packages.contracts.rag import ChunkType, RAGContext, RetrievalResult
from packages.core.interfaces.embeddings import BaseEmbeddingProvider
from services.rag.context_assembler import ContextAssembler
from services.rag.ingestion.indexer import DocumentIndexer
from services.rag.stores.sqlite_rag_store import SQLiteRAGStore


class RAGRetriever:
    """Unified facade for document indexing, hybrid search, and context assembly."""

    def __init__(
        self,
        rag_store: SQLiteRAGStore | None = None,
        db_path: str = "data/persistence/pixel_rag.db",
        embedding_provider: BaseEmbeddingProvider | None = None,
    ) -> None:
        self.rag_store = rag_store or SQLiteRAGStore(
            db_path=db_path, embedding_provider=embedding_provider
        )
        self.indexer = DocumentIndexer(rag_store=self.rag_store)

    async def index_text(
        self,
        text: str,
        source_uri: str = "raw_input",
        is_code: bool = False,
    ) -> int:
        """Indexes an in-memory document or code snippet."""
        chunk_type = ChunkType.CODE_AST if is_code else ChunkType.TEXT_PARAGRAPH
        return await self.indexer.index_text(
            text=text, source_uri=source_uri, chunk_type=chunk_type
        )

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.1,
    ) -> list[RetrievalResult]:
        """Performs hybrid dense vector and lexical search."""
        return await self.rag_store.search_hybrid(
            query=query,
            limit=top_k,
            min_similarity=min_similarity,
        )

    async def retrieve_context(
        self,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.1,
        max_context_chars: int = 4000,
    ) -> RAGContext:
        """Searches knowledge base and returns cited RAGContext."""
        results = await self.rag_store.search_hybrid(
            query=query,
            limit=limit,
            min_similarity=min_similarity,
        )
        return ContextAssembler.assemble_context(
            query=query,
            retrieval_results=results,
            max_context_chars=max_context_chars,
        )

    async def retrieve_and_assemble(
        self,
        query: str,
        max_tokens: int = 1000,
        top_k: int = 5,
    ) -> RAGContext:
        """Retrieves and formats cited context bounded by token estimate (4 chars/token)."""
        max_chars = max_tokens * 4
        return await self.retrieve_context(
            query=query,
            limit=top_k,
            max_context_chars=max_chars,
        )
