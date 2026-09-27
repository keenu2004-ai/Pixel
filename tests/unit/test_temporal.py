"""Unit tests for bilingual temporal intent resolution."""

from datetime import datetime

from packages.core.temporal import TemporalResolver


def test_resolve_hindi_tomorrow_morning() -> None:
    ref_time = datetime(2026, 9, 27, 15, 0, 0)
    # "kal subah 7 baje" -> 2026-09-28 07:00:00
    res = TemporalResolver.resolve_datetime("Hey Pixel, kal subah 7 baje alarm laga dena", ref_time)
    assert res is not None
    assert res.year == 2026
    assert res.month == 9
    assert res.day == 28
    assert res.hour == 7
    assert res.minute == 0


def test_resolve_english_evening() -> None:
    ref_time = datetime(2026, 9, 27, 10, 0, 0)
    # "tomorrow 6 pm" -> 2026-09-28 18:00:00
    res = TemporalResolver.resolve_datetime("Remind me tomorrow 6 pm", ref_time)
    assert res is not None
    assert res.day == 28
    assert res.hour == 18
    assert res.minute == 0


def test_resolve_parso_night() -> None:
    ref_time = datetime(2026, 9, 27, 12, 0, 0)
    # "parso raat 9 baje" -> 2026-09-29 21:00:00
    res = TemporalResolver.resolve_datetime("Parso raat 9 baje dinner ka reminder daal do", ref_time)
    assert res is not None
    assert res.day == 29
    assert res.hour == 21
    assert res.minute == 0
