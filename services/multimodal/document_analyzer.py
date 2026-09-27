"""PIXEL — Phase 16 Document Visual Analyzer.

Extracts structured text, technical tables, diagrams, and figures from visual
document frames and scanned pages.
"""

from typing import Any

from packages.contracts.multimodal import DocumentVisualFrame
from services.multimodal.ocr_engine import MultilingualOCREngine
from services.multimodal.providers.base import BaseDocumentVisualProvider


class DocumentVisualAnalyzer:
    """Parses technical documents, forms, and tables visually."""

    def __init__(
        self,
        ocr_engine: MultilingualOCREngine | None = None,
        provider: BaseDocumentVisualProvider | None = None,
    ) -> None:
        self._ocr_engine = ocr_engine or MultilingualOCREngine()
        self._provider = provider

    async def analyze_document(
        self,
        document_frame: DocumentVisualFrame,
    ) -> dict[str, Any]:
        """Performs visual document analysis on a single document page frame."""
        if self._provider:
            return await self._provider.analyze_document_page(document_frame)

        # Heuristic document parsing
        ocr_result = await self._ocr_engine.extract_text(document_frame.raw_bytes_base64)

        tables_detected: list[dict[str, Any]] = []
        # Check if text contains tabular indicators (pipes, tabs, aligned commas)
        if "|" in ocr_result.full_text or "\t" in ocr_result.full_text:
            tables_detected.append(
                {
                    "table_id": "tbl_01",
                    "rows_count": len(ocr_result.blocks),
                    "columns_count": 3,
                    "confidence": 0.95,
                }
            )

        return {
            "document_id": document_frame.document_id,
            "page_number": document_frame.page_number,
            "total_pages": document_frame.total_pages,
            "full_text": ocr_result.full_text,
            "detected_tables": tables_detected,
            "detected_figures_count": 1 if "diagram" in ocr_result.full_text.lower() else 0,
            "confidence": ocr_result.confidence,
            "is_untrusted_data": True,
        }
