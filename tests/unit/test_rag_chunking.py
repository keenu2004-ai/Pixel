"""Unit tests for AST-Aware Code & Markdown Chunkers."""


from packages.contracts.rag import ChunkType
from services.rag.chunking.ast_chunker import ASTCodeChunker
from services.rag.chunking.markdown_chunker import MarkdownChunker


def test_ast_python_code_chunking() -> None:
    code = '''"""Sample module docstring."""

import os
import sys

def calculate_metric(a: int, b: int) -> int:
    """Calculates a sample metric."""
    result = a + b
    return result

class AudioPipeline:
    """Manages audio streaming."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate

    def process(self, frame: bytes) -> bool:
        return len(frame) > 0
'''

    chunker = ASTCodeChunker()
    chunks = chunker.chunk_text(code, source_uri="src/audio.py")

    assert len(chunks) >= 2  # calculate_metric, AudioPipeline (with methods)

    # Check for function symbol
    func_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE_AST and c.symbol_name == "calculate_metric"]
    assert len(func_chunks) == 1
    assert func_chunks[0].start_line == 6
    assert "def calculate_metric" in func_chunks[0].content

    # Check for class symbol
    class_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE_AST and c.symbol_name == "AudioPipeline"]
    assert len(class_chunks) == 1
    assert "class AudioPipeline" in class_chunks[0].content
    assert "def process" in class_chunks[0].content


def test_ast_syntax_error_fallback() -> None:
    malformed_code = """
def broken_syntax(x, y:
    return x +
"""
    chunker = ASTCodeChunker()
    chunks = chunker.chunk_text(malformed_code, source_uri="src/broken.py")

    # Should safely fallback to general text chunk rather than crashing
    assert len(chunks) >= 1
    assert "broken_syntax" in chunks[0].content


def test_markdown_header_chunking() -> None:
    markdown = """# Architecture Overview

PIXEL is a personal voice-first AI operating layer.

## Voice Pipeline

The voice pipeline handles wake word and streaming STT.
Latency is strictly bounded under 600ms for deterministic paths.

## Memory Architecture

5-tier memory model:
- Working Memory
- Episodic Memory
- Semantic Facts

### PII Protection

Secrets and credentials are never persisted.
"""

    chunker = MarkdownChunker()
    chunks = chunker.chunk_text(markdown, source_uri="docs/architecture.md")

    assert len(chunks) >= 3
    section_titles = [c.symbol_name for c in chunks if c.symbol_name]
    assert any("Voice Pipeline" in t for t in section_titles)
    assert any("Memory Architecture" in t for t in section_titles)
    assert any("PII Protection" in t for t in section_titles)
