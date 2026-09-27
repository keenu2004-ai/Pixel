"""PIXEL — Phase 16 Multilingual OCR Engine.

Handles text recognition for English, Hindi (Devanagari), Hinglish, code snippets,
URLs, numbers, and technical logs.
Enforces that all extracted text is tagged as UNTRUSTED EXTERNAL DATA.
"""

import re
import time

from packages.contracts.multimodal import (
    OCRBlock,
    OCRLine,
    OCRResult,
    OCRWord,
    VisualBoundingBox,
)
from services.multimodal.providers.base import BaseOCRProvider


class MultilingualOCREngine:
    """Production multilingual OCR engine."""

    def __init__(self, provider: BaseOCRProvider | None = None) -> None:
        self._provider = provider

    def detect_languages(self, text: str) -> list[str]:
        """Detects whether text contains English, Devanagari Hindi, Hinglish, or Code."""
        langs = set()
        # Devanagari Unicode range: \u0900-\u097F
        if re.search(r"[\u0900-\u097F]", text):
            langs.add("hi")

        # Hinglish / English indicators
        hinglish_keywords = {
            "ye",
            "yeh",
            "kya",
            "karo",
            "hai",
            "nahi",
            "isme",
            "mujhe",
            "bata",
            "kar",
            "pe",
            "kaise",
        }
        words_lower = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
        if words_lower.intersection(hinglish_keywords):
            langs.add("hinglish")
        elif re.search(r"[a-zA-Z]", text):
            langs.add("en")

        # Code indicators
        if re.search(
            r"(def |class |function |const |import |from |return |=>|===|;\s*$)", text, re.MULTILINE
        ):
            langs.add("code")

        return sorted(list(langs)) if langs else ["en"]

    async def extract_text(
        self,
        raw_text_or_base64: str,
        target_languages: list[str] | None = None,
        orientation_degrees: float = 0.0,
    ) -> OCRResult:
        """Processes and extracts structured OCR tokens and geometry."""
        start_time = time.perf_counter()

        if self._provider:
            res = await self._provider.extract_text(raw_text_or_base64, target_languages)
            res.orientation_degrees = orientation_degrees
            return res

        # Fallback heuristic parser for testing and direct text analysis
        text_content = raw_text_or_base64.strip()
        lines_raw = [line.strip() for line in text_content.splitlines() if line.strip()]
        if not lines_raw:
            lines_raw = [text_content] if text_content else ["No text detected"]

        detected_langs = self.detect_languages(text_content)
        blocks: list[OCRBlock] = []

        total_lines = len(lines_raw)
        for idx, line_str in enumerate(lines_raw):
            y_start = idx / max(total_lines, 1)
            y_end = (idx + 1) / max(total_lines, 1)

            words_in_line = line_str.split()
            ocr_words: list[OCRWord] = []
            num_words = len(words_in_line)

            for w_idx, w_text in enumerate(words_in_line):
                x_start = w_idx / max(num_words, 1)
                x_end = (w_idx + 1) / max(num_words, 1)

                w_bbox = VisualBoundingBox(
                    x_min=round(x_start, 3),
                    y_min=round(y_start, 3),
                    x_max=round(x_end, 3),
                    y_max=round(y_end, 3),
                    abs_x=int(x_start * 1920),
                    abs_y=int(y_start * 1080),
                    abs_width=int((x_end - x_start) * 1920),
                    abs_height=int((y_end - y_start) * 1080),
                )
                ocr_words.append(OCRWord(text=w_text, bounding_box=w_bbox, confidence=0.99))

            line_bbox = VisualBoundingBox(
                x_min=0.05,
                y_min=round(y_start, 3),
                x_max=0.95,
                y_max=round(y_end, 3),
                abs_x=96,
                abs_y=int(y_start * 1080),
                abs_width=1728,
                abs_height=int((y_end - y_start) * 1080),
            )
            ocr_line = OCRLine(
                text=line_str, words=ocr_words, bounding_box=line_bbox, confidence=0.99
            )
            block = OCRBlock(
                text=line_str,
                lines=[ocr_line],
                bounding_box=line_bbox,
                language=detected_langs[0] if detected_langs else "en",
                confidence=0.99,
            )
            blocks.append(block)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return OCRResult(
            full_text=text_content,
            blocks=blocks,
            detected_languages=detected_langs,
            confidence=0.99 if text_content else 0.5,
            orientation_degrees=orientation_degrees,
            latency_ms=elapsed_ms,
            is_untrusted_data=True,  # Invariant: OCR is UNTRUSTED data
        )
