"""Unit tests for Bilingual Deterministic Intent Parser."""

from datetime import datetime

from packages.contracts.deterministic import (
    AlarmAction,
    AppAction,
    ReminderAction,
    SystemQueryType,
    TimerAction,
    VolumeAction,
)
from packages.contracts.intents import IntentRoutingType
from services.intent_engine.parser import DeterministicIntentParser


def test_timer_english_parsing() -> None:
    packet = DeterministicIntentParser.parse_intent("set a timer for 10 minutes")
    assert packet.routing_type == IntentRoutingType.DETERMINISTIC_FAST_PATH
    assert packet.target_intent == "TIMER"
    assert packet.extracted_entities["action"] == TimerAction.SET
    assert packet.extracted_entities["duration_seconds"] == 600


def test_timer_hinglish_parsing() -> None:
    packet = DeterministicIntentParser.parse_intent("10 minute ka timer laga do")
    assert packet.routing_type == IntentRoutingType.DETERMINISTIC_FAST_PATH
    assert packet.target_intent == "TIMER"
    assert packet.extracted_entities["action"] == TimerAction.SET
    assert packet.extracted_entities["duration_seconds"] == 600

    # Hindi fractional durations: "aadha ghanta" = 1800s (30 mins)
    packet2 = DeterministicIntentParser.parse_intent("aadha ghanta ka timer shuru karo")
    assert packet2.extracted_entities["duration_seconds"] == 1800


def test_timer_cancel_and_status() -> None:
    p_cancel = DeterministicIntentParser.parse_intent("timer cancel kar do")
    assert p_cancel.extracted_entities["action"] == TimerAction.CANCEL

    p_status = DeterministicIntentParser.parse_intent("timer kitna bacha hai")
    assert p_status.extracted_entities["action"] == TimerAction.STATUS


def test_alarm_english_and_hindi() -> None:
    ref_time = datetime(2026, 9, 27, 10, 0, 0)

    # English
    p_en = DeterministicIntentParser.parse_intent("set an alarm for 7 am tomorrow", reference_time=ref_time)
    assert p_en.target_intent == "ALARM"
    assert p_en.extracted_entities["action"] == AlarmAction.SET
    assert "07:00 AM" in p_en.extracted_entities["time_str"]

    # Hindi / Hinglish: "kal subah 7 baje alarm laga dena"
    p_hi = DeterministicIntentParser.parse_intent("kal subah 7 baje alarm laga dena", reference_time=ref_time)
    assert p_hi.target_intent == "ALARM"
    assert p_hi.extracted_entities["action"] == AlarmAction.SET
    assert "07:00 AM" in p_hi.extracted_entities["time_str"]


def test_reminder_bilingual() -> None:
    ref_time = datetime(2026, 9, 27, 10, 0, 0)

    p_en = DeterministicIntentParser.parse_intent("remind me to call mom in 30 minutes", reference_time=ref_time)
    assert p_en.target_intent == "REMINDER"
    assert p_en.extracted_entities["action"] == ReminderAction.SET

    p_hi = DeterministicIntentParser.parse_intent("mujhe shaam 7 baje doodh lene ka reminder set karo", reference_time=ref_time)
    assert p_hi.target_intent == "REMINDER"
    assert p_hi.extracted_entities["action"] == ReminderAction.SET


def test_volume_adjustments() -> None:
    p1 = DeterministicIntentParser.parse_intent("volume 50 percent karo")
    assert p1.target_intent == "VOLUME"
    assert p1.extracted_entities["action"] == VolumeAction.SET
    assert p1.extracted_entities["level"] == 50

    p2 = DeterministicIntentParser.parse_intent("awaaz badhao")
    assert p2.extracted_entities["action"] == VolumeAction.INCREASE

    p3 = DeterministicIntentParser.parse_intent("volume kam kar do")
    assert p3.extracted_entities["action"] == VolumeAction.DECREASE

    p4 = DeterministicIntentParser.parse_intent("mute kar do")
    assert p4.extracted_entities["action"] == VolumeAction.MUTE

    p5 = DeterministicIntentParser.parse_intent("unmute audio")
    assert p5.extracted_entities["action"] == VolumeAction.UNMUTE


def test_app_launch() -> None:
    p_open = DeterministicIntentParser.parse_intent("Chrome kholo")
    assert p_open.target_intent == "APP_LAUNCH"
    assert p_open.extracted_entities["action"] == AppAction.OPEN
    assert p_open.extracted_entities["app_name"] == "chrome"

    p_close = DeterministicIntentParser.parse_intent("close calculator")
    assert p_close.target_intent == "APP_LAUNCH"
    assert p_close.extracted_entities["action"] == AppAction.CLOSE
    assert p_close.extracted_entities["app_name"] == "calculator"


def test_system_queries() -> None:
    p_time = DeterministicIntentParser.parse_intent("kitne baje hain")
    assert p_time.target_intent == "SYSTEM_QUERY"
    assert p_time.extracted_entities["query_type"] == SystemQueryType.TIME

    p_date = DeterministicIntentParser.parse_intent("what is the date today")
    assert p_date.target_intent == "SYSTEM_QUERY"
    assert p_date.extracted_entities["query_type"] == SystemQueryType.DATE

    p_bat = DeterministicIntentParser.parse_intent("battery status")
    assert p_bat.target_intent == "SYSTEM_QUERY"
    assert p_bat.extracted_entities["query_type"] == SystemQueryType.BATTERY


def test_conversational_fallback() -> None:
    p_qa = DeterministicIntentParser.parse_intent("Who was the first person on the moon?")
    assert p_qa.routing_type == IntentRoutingType.CONVERSATIONAL_QA
    assert p_qa.target_intent == "CONVERSATIONAL"
