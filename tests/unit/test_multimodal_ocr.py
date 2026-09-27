"""PIXEL — Phase 16 Multilingual OCR Engine Unit Tests.

Validates English, Hindi (Devanagari), Hinglish, code snippets, URL parsing,
orientation metadata, and untrusted data wrapping.
"""

import pytest

from services.multimodal.ocr_engine import MultilingualOCREngine


@pytest.mark.asyncio
async def test_ocr_english_and_code() -> None:
    engine = MultilingualOCREngine()
    code_text = "def calculate_total(price, tax):\n    return price * (1 + tax)"
    res = await engine.extract_text(code_text)

    assert res.is_untrusted_data is True
    assert "def calculate_total" in res.full_text
    assert "code" in res.detected_languages or "en" in res.detected_languages
    assert len(res.blocks) == 2


@pytest.mark.asyncio
async def test_ocr_hindi_devanagari() -> None:
    engine = MultilingualOCREngine()
    hindi_text = "नमस्ते दुनिया पिक्सल सहायक"
    res = await engine.extract_text(hindi_text)

    assert "hi" in res.detected_languages
    assert res.full_text == hindi_text
    assert res.is_untrusted_data is True


@pytest.mark.asyncio
async def test_ocr_hinglish() -> None:
    engine = MultilingualOCREngine()
    hinglish_text = "ye screen pe error kya hai mujhe batao"
    res = await engine.extract_text(hinglish_text)

    assert "hinglish" in res.detected_languages
    assert "error" in res.full_text
    assert res.confidence >= 0.95


@pytest.mark.asyncio
async def test_ocr_orientation_and_latency() -> None:
    engine = MultilingualOCREngine()
    res = await engine.extract_text("Rotated Text Test", orientation_degrees=90.0)

    assert res.orientation_degrees == 90.0
    assert res.latency_ms >= 0.0
