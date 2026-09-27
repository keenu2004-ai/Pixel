"""Document and Codebase Ingestion Indexer.

Automates file ingestion, AST/Markdown chunking, vector embedding, and storage.
"""

import logging
from pathlib import Path
from uuid import uuid4

from packages.contracts.rag import ChunkType
from services.rag.chunking.ast_chunker import ASTCodeChunker
from services.rag.chunking.markdown_chunker import MarkdownChunker
from services.rag.stores.sqlite_rag_store import SQLiteRAGStore

logger = logging.getLogger(__name__)


class DocumentIndexer:
    """Ingests and indexes documents and codebases into the RAG knowledge store."""

    def __init__(self, rag_store: SQLiteRAGStore) -> None:
        self.rag_store = rag_store

    async def index_text(
        self,
        text: str,
        document_id: str | None = None,
        source_uri: str = "raw_input",
        chunk_type: ChunkType = ChunkType.TEXT_PARAGRAPH,
    ) -> int:
        """Chunks and indexes an in-memory string."""
        doc_id = document_id or f"doc_{uuid4().hex[:8]}"

        if chunk_type == ChunkType.CODE_AST or source_uri.endswith(".py"):
            chunks = ASTCodeChunker.chunk_python_code(text, source_uri=source_uri, document_id=doc_id)
        else:
            chunks = MarkdownChunker.chunk_markdown(text, source_uri=source_uri, document_id=doc_id)

        return await self.rag_store.add_chunks(chunks)

    async def index_file(self, file_path: str | Path, document_id: str | None = None) -> int:
        """Reads a local file and indexes its chunks."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            logger.warning("File %s does not exist for indexing.", file_path)
            return 0

        doc_id = document_id or path.stem
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as err:
            logger.error("Failed to read %s for indexing: %s", path, err)
            return 0

        if path.suffix == ".py":
            chunks = ASTCodeChunker.chunk_python_code(content, source_uri=str(path), document_id=doc_id)
        else:
            chunks = MarkdownChunker.chunk_markdown(content, source_uri=str(path), document_id=doc_id)

        return await self.rag_store.add_chunks(chunks)

    async def index_directory(self, dir_path: str | Path, extensions: tuple[str, ...] = (".py", ".md", ".txt")) -> int:
        """Indexes all matching files in a directory."""
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            return 0

        total_indexed = 0
        for ext in extensions:
            for file_p in path.glob(f"**/*{ext}"):
                if file_p.is_file():
                    total_indexed += await self.index_file(file_p)

        return total_indexed
