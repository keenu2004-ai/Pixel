"""AST-Aware Python Code Chunker.

Parses source code into structurally sound AST blocks (classes, methods, functions)
preserving line numbers, symbol names, and syntactic boundaries.
"""

import ast
import hashlib
import logging

from packages.contracts.rag import ChunkType, DocumentChunk

logger = logging.getLogger(__name__)


class ASTCodeChunker:
    """Extracts function, method, and class chunks from Python source files."""

    @classmethod
    def chunk_python_code(
        cls,
        code_text: str,
        source_uri: str,
        document_id: str,
    ) -> list[DocumentChunk]:
        """Parses python source and returns list of DocumentChunk instances."""
        chunks: list[DocumentChunk] = []
        lines = code_text.splitlines(keepends=True)
        if not lines:
            return chunks

        try:
            tree = ast.parse(code_text, filename=source_uri)
        except SyntaxError as err:
            logger.warning("SyntaxError in %s, falling back to line chunker: %s", source_uri, err)
            # Fallback for non-compliant code
            chunk_hash = hashlib.sha256(code_text.encode("utf-8")).hexdigest()
            return [
                DocumentChunk(
                    document_id=document_id,
                    source_uri=source_uri,
                    content=code_text,
                    chunk_type=ChunkType.CODE_AST,
                    start_line=1,
                    end_line=len(lines),
                    symbol_name="<module_fallback>",
                    chunk_hash=chunk_hash,
                )
            ]

        # Walk top-level nodes
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno
                end = node.end_lineno or start
                chunk_lines = lines[start - 1 : end]
                content = "".join(chunk_lines).strip()
                symbol_name = node.name
                chunk_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                chunks.append(
                    DocumentChunk(
                        document_id=document_id,
                        source_uri=source_uri,
                        content=content,
                        chunk_type=ChunkType.CODE_AST,
                        start_line=start,
                        end_line=end,
                        symbol_name=symbol_name,
                        chunk_hash=chunk_hash,
                        metadata={"node_type": type(node).__name__},
                    )
                )

        # If no classes or functions found (e.g. script), chunk entire module
        if not chunks:
            content = code_text.strip()
            chunk_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    source_uri=source_uri,
                    content=content,
                    chunk_type=ChunkType.CODE_AST,
                    start_line=1,
                    end_line=len(lines),
                    symbol_name="<module>",
                    chunk_hash=chunk_hash,
                )
            )

        return chunks

    @classmethod
    def chunk_text(
        cls,
        code_text: str,
        source_uri: str = "code.py",
        document_id: str = "doc_code",
    ) -> list[DocumentChunk]:
        """Chunking method alias."""
        return cls.chunk_python_code(
            code_text=code_text, source_uri=source_uri, document_id=document_id
        )
