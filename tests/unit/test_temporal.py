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


def test_resolve_relative_minutes_offset() -> None:
    ref_time = datetime(2026, 9, 27, 14, 15, 0)
    # "in 20 minutes" -> 14:35:00
    res = TemporalResolver.resolve_datetime("remind me in 20 minutes to check deployment", ref_time)
    assert res is not None
    assert res.hour == 14
    assert res.minute == 35


def test_resolve_relative_minutes_hindi() -> None:
    ref_time = datetime(2026, 9, 27, 14, 15, 0)
    # "15 minute baad" -> 14:30:00
    res = TemporalResolver.resolve_datetime("15 minute baad timer bajana", ref_time)
    assert res is not None
    assert res.hour == 14
    assert res.minute == 30


def test_resolve_relative_hours() -> None:
    ref_time = datetime(2026, 9, 27, 10, 0, 0)
    # "in 2 hours" -> 12:00:00
    res = TemporalResolver.resolve_datetime("remind me in 2 hours", ref_time)
    assert res is not None
    assert res.hour == 12
    assert res.minute == 0


def test_resolve_next_weekday() -> None:
    # 2026-09-27 is Sunday (weekday 6)
    ref_time = datetime(2026, 9, 27, 10, 0, 0)
    # "agla somwar subah 9 baje" -> next Monday (2026-09-28) 09:00:00
    res = TemporalResolver.resolve_datetime("agla somwar 9 am meeting hai", ref_time)
    assert res is not None
    assert res.day == 28
    assert res.hour == 9


def test_unparseable_query_returns_none() -> None:
    res = TemporalResolver.resolve_datetime("what is the weather in Delhi right now")
    assert res is None
