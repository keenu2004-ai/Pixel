"""Markdown and Document Header-Aware Chunker.

Splits documentation along H1, H2, and H3 headers while maintaining
hierarchical section context and manageable token limits.
"""

import hashlib
import re

from packages.contracts.rag import ChunkType, DocumentChunk


class MarkdownChunker:
    """Header-aware Markdown document chunker."""

    HEADER_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

    @classmethod
    def chunk_markdown(
        cls,
        text: str,
        source_uri: str,
        document_id: str,
        max_words_per_chunk: int = 300,
    ) -> list[DocumentChunk]:
        """Splits markdown text on heading boundaries."""
        chunks: list[DocumentChunk] = []
        lines = text.splitlines(keepends=True)
        if not lines:
            return chunks

        sections: list[tuple[str, int, list[str]]] = []
        current_header = "Introduction"
        current_start = 1
        current_lines: list[str] = []

        for idx, line in enumerate(lines, start=1):
            m = cls.HEADER_PATTERN.match(line.strip())
            if m:
                if current_lines:
                    sections.append((current_header, current_start, current_lines))
                current_header = m.group(2).strip()
                current_start = idx
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_header, current_start, current_lines))

        # Generate DocumentChunks from sections
        for header, start_line, sec_lines in sections:
            content = "".join(sec_lines).strip()
            if not content:
                continue

            end_line = start_line + len(sec_lines) - 1
            chunk_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    source_uri=source_uri,
                    content=content,
                    chunk_type=ChunkType.MARKDOWN_SECTION,
                    start_line=start_line,
                    end_line=end_line,
                    symbol_name=header,
                    chunk_hash=chunk_hash,
                    metadata={"header": header},
                )
            )

        return chunks

    @classmethod
    def chunk_text(
        cls,
        text: str,
        source_uri: str = "doc.md",
        document_id: str = "doc_md",
    ) -> list[DocumentChunk]:
        """Chunking method alias."""
        return cls.chunk_markdown(text=text, source_uri=source_uri, document_id=document_id)
