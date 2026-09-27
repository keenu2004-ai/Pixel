"""RAG Knowledge Ingestion and Retrieval Contracts.

Defines schemas for Document Chunks, Citations, Vector Retrieval, and Assembled Context.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ChunkType(StrEnum):
    """Categorization of indexed knowledge chunks."""

    MARKDOWN_SECTION = "MARKDOWN_SECTION"
    CODE_AST = "CODE_AST"
    TEXT_PARAGRAPH = "TEXT_PARAGRAPH"
    TABLE = "TABLE"


class DocumentChunk(BaseModel):
    """A semantic chunk of a document or codebase symbol."""

    chunk_id: str = Field(default_factory=_gen_id, description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document identifier")
    source_uri: str = Field(..., description="File path or URL origin of the source")
    content: str = Field(..., description="Text or source code body of the chunk")
    chunk_type: ChunkType = Field(
        default=ChunkType.TEXT_PARAGRAPH, description="Structural chunk category"
    )
    start_line: int | None = Field(default=None, ge=1, description="Start line in source file")
    end_line: int | None = Field(default=None, ge=1, description="End line in source file")
    symbol_name: str | None = Field(
        default=None, description="AST function/class/method symbol name"
    )
    chunk_hash: str = Field(..., description="SHA-256 hash of the content")
    embedding: list[float] = Field(default_factory=list, description="Dense vector embedding")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary structural metadata"
    )
    created_at: datetime = Field(default_factory=_utc_now)


class RetrievalResult(BaseModel):
    """A single retrieved item with similarity score and citation metadata."""

    chunk: DocumentChunk = Field(..., description="Retrieved document chunk")
    score: float = Field(..., ge=0.0, le=1.0, description="Composite hybrid relevance score")
    citation_id: str = Field(default_factory=_gen_id, description="Citation anchor (e.g. [^1])")


class RAGContext(BaseModel):
    """Complete assembled context ready for injection into prompt context."""

    query: str = Field(..., description="Original user question or search query")
    retrieved_items: list[RetrievalResult] = Field(
        default_factory=list, description="Top-k retrieved results"
    )
    formatted_context: str = Field(
        ..., description="Sanitized, prompt-injection safe context block"
    )
    total_tokens_approx: int = Field(
        default=0, ge=0, description="Approximate token count of context"
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list, description="Structured citation references"
    )
