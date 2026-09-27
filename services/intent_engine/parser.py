"""Bilingual Deterministic Intent Parser and Entity Extractor.

Parses natural English, Hindi, and Hinglish utterances into typed IntentPackets
and deterministic intent schemas without requiring external LLM tokens.
"""

import logging
import re
from datetime import datetime, timedelta

from packages.contracts.deterministic import (
    AlarmAction,
    AlarmIntentData,
    AppAction,
    AppLaunchIntentData,
    ReminderAction,
    ReminderIntentData,
    SystemQueryIntentData,
    SystemQueryType,
    TimerAction,
    TimerIntentData,
    VolumeAction,
    VolumeIntentData,
)
from packages.contracts.intents import IntentPacket, IntentRoutingType
from packages.core.temporal import TemporalResolver

logger = logging.getLogger(__name__)


class DeterministicIntentParser:
    """Fast-path deterministic intent parser (<5ms execution)."""

    # Application name aliases and mappings
    APP_ALIASES: dict[str, str] = {
        "chrome": "chrome",
        "google chrome": "chrome",
        "browser": "chrome",
        "notepad": "notepad",
        "text editor": "notepad",
        "calculator": "calculator",
        "calc": "calculator",
        "spotify": "spotify",
        "music": "spotify",
        "vscode": "vscode",
        "code": "vscode",
        "visual studio code": "vscode",
        "terminal": "terminal",
        "cmd": "terminal",
        "powershell": "terminal",
        "explorer": "explorer",
        "files": "explorer",
        "file manager": "explorer",
        "settings": "settings",
    }

    @classmethod
    def parse_duration_seconds(cls, text: str) -> int:
        """Extracts duration in seconds from English/Hindi/Hinglish text."""
        total_seconds = 0
        norm = text.lower().strip()

        # Hindi phrases: "aadha ghanta" (half hour), "dedh ghanta" (1.5 hours), "dhai ghante" (2.5 hours)
        if "aadha ghanta" in norm or "aadhe ghante" in norm or "half hour" in norm or "half an hour" in norm:
            total_seconds += 1800
        if "dedh ghanta" in norm or "dedh ghante" in norm:
            total_seconds += 5400
        if "dhai ghanta" in norm or "dhai ghante" in norm:
            total_seconds += 9000
        if "ek ghanta" in norm or "one hour" in norm or "an hour" in norm:
            total_seconds += 3600

        # Hours match
        hr_match = re.search(r"(\d+)\s*(?:hours?|hrs?|ghante|ghanta)\b", norm)
        if hr_match:
            total_seconds += int(hr_match.group(1)) * 3600

        # Minutes match
        min_match = re.search(r"(\d+)\s*(?:minutes?|mins?|minute)\b", norm)
        if min_match:
            total_seconds += int(min_match.group(1)) * 60

        # Seconds match
        sec_match = re.search(r"(\d+)\s*(?:seconds?|secs?|second)\b", norm)
        if sec_match:
            total_seconds += int(sec_match.group(1))

        # Bare numbers after "timer for X" / "X ka timer"
        if total_seconds == 0:
            bare_match = re.search(r"(?:timer\s+(?:for\s+)?|(\d+)\s*ka\s+timer)(\d+)?", norm)
            if bare_match:
                val = bare_match.group(2) or bare_match.group(1)
                if val and val.isdigit():
                    # Default bare number to minutes
                    total_seconds = int(val) * 60

        return total_seconds

    @classmethod
    def parse_intent(
        cls,
        text: str,
        session_id: str | None = None,
        reference_time: datetime | None = None,
    ) -> IntentPacket:
        """Parses an utterance into an IntentPacket with normalized entity payloads."""
        norm = text.lower().strip()
        ref_time = reference_time or datetime.now()

        # 1. Timer Intent
        timer_data = cls._match_timer(norm)
        if timer_data is not None:
            return IntentPacket(
                raw_query=text,
                language="hi" if any(w in norm for w in ["karo", "laga", "shuru", "band", "kitna"]) else "en",
                routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
                target_intent="TIMER",
                extracted_entities=timer_data.model_dump(),
                confidence=0.98,
                session_id=session_id,
            )

        # 2. Alarm Intent
        alarm_data = cls._match_alarm(norm, ref_time)
        if alarm_data is not None:
            return IntentPacket(
                raw_query=text,
                language="hi" if any(w in norm for w in ["karo", "laga", "utha", "subah", "shaam", "baje"]) else "en",
                routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
                target_intent="ALARM",
                extracted_entities=alarm_data.model_dump(),
                confidence=0.98,
                session_id=session_id,
            )

        # 3. Reminder Intent
        reminder_data = cls._match_reminder(norm, ref_time)
        if reminder_data is not None:
            return IntentPacket(
                raw_query=text,
                language="hi" if any(w in norm for w in ["yaad", "dilao", "dila", "karo", "subah", "shaam"]) else "en",
                routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
                target_intent="REMINDER",
                extracted_entities=reminder_data.model_dump(),
                confidence=0.95,
                session_id=session_id,
            )

        # 4. Volume / Media Control Intent
        volume_data = cls._match_volume(norm)
        if volume_data is not None:
            return IntentPacket(
                raw_query=text,
                language="hi" if any(w in norm for w in ["awaaz", "badhao", "kam", "karo", "band"]) else "en",
                routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
                target_intent="VOLUME",
                extracted_entities=volume_data.model_dump(),
                confidence=0.98,
                session_id=session_id,
            )

        # 5. Application Launch Intent
        app_data = cls._match_app_launch(norm)
        if app_data is not None:
            return IntentPacket(
                raw_query=text,
                language="hi" if any(w in norm for w in ["kholo", "chalao", "band", "karo"]) else "en",
                routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
                target_intent="APP_LAUNCH",
                extracted_entities=app_data.model_dump(),
                confidence=0.95,
                session_id=session_id,
            )

        # 6. System Query (Time / Date / Battery / Status)
        sys_data = cls._match_system_query(norm)
        if sys_data is not None:
            return IntentPacket(
                raw_query=text,
                language="hi" if any(w in norm for w in ["kya", "kitne", "baje", "taareekh", "samay", "hai"]) else "en",
                routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
                target_intent="SYSTEM_QUERY",
                extracted_entities=sys_data.model_dump(),
                confidence=0.99,
                session_id=session_id,
            )

        # Fallback to Conversational QA
        return IntentPacket(
            raw_query=text,
            language="en",
            routing_type=IntentRoutingType.CONVERSATIONAL_QA,
            target_intent="CONVERSATIONAL",
            extracted_entities={},
            confidence=0.50,
            session_id=session_id,
        )

    @classmethod
    def _match_timer(cls, text: str) -> TimerIntentData | None:
        """Matches timer commands."""
        if not ("timer" in text or "taimar" in text):
            return None

        # Check cancel/stop
        if any(w in text for w in ["cancel", "stop", "delete", "clear", "band", "hatao"]):
            return TimerIntentData(action=TimerAction.CANCEL)

        # Check status
        if any(w in text for w in ["status", "how much left", "kitna bacha", "bache", "kitna time"]):
            return TimerIntentData(action=TimerAction.STATUS)

        # Parse duration
        duration_sec = cls.parse_duration_seconds(text)
        if duration_sec > 0:
            return TimerIntentData(action=TimerAction.SET, duration_seconds=duration_sec)

        return None

    @classmethod
    def _match_alarm(cls, text: str, ref_time: datetime) -> AlarmIntentData | None:
        """Matches alarm commands."""
        is_alarm_phrase = any(w in text for w in ["alarm", "alaram", "wake me up", "utha dena", "uthana", "wake up"])
        if not is_alarm_phrase:
            return None

        # Check list
        if any(w in text for w in ["list", "show", "tell", "dikhao", "batao", "konse"]) and not any(w in text for w in ["set", "laga", "create"]):
            return AlarmIntentData(action=AlarmAction.LIST)

        # Check cancel
        if any(w in text for w in ["cancel", "delete", "remove", "turn off", "stop", "band", "hatao"]):
            return AlarmIntentData(action=AlarmAction.CANCEL)

        # Resolve target alarm datetime
        target_dt = TemporalResolver.resolve_datetime(text, reference_time=ref_time)
        if target_dt is not None:
            # If resolved time is in the past for today, advance to tomorrow
            if target_dt <= ref_time and "kal" not in text and "tomorrow" not in text:
                target_dt += timedelta(days=1)

            return AlarmIntentData(
                action=AlarmAction.SET,
                target_time=target_dt,
                time_str=target_dt.strftime("%I:%M %p"),
                label="Morning Alarm" if target_dt.hour < 12 else "Alarm",
            )

        return None

    @classmethod
    def _match_reminder(cls, text: str, ref_time: datetime) -> ReminderIntentData | None:
        """Matches reminder commands."""
        is_reminder = any(w in text for w in ["remind", "reminder", "yaad dilana", "yaad dilao", "yaad dila dena"])
        if not is_reminder:
            return None

        # Check list
        if any(w in text for w in ["list", "show", "dikhao", "batao"]) and not any(w in text for w in ["set", "create", "karo", "dilao"]):
            return ReminderIntentData(action=ReminderAction.LIST, text="")

        # Check cancel
        if any(w in text for w in ["cancel", "delete", "clear", "band", "hatao"]):
            return ReminderIntentData(action=ReminderAction.CANCEL, text="")

        # Extract target time and reminder content
        target_dt = TemporalResolver.resolve_datetime(text, reference_time=ref_time)
        if target_dt is None:
            # Default reminder to 1 hour from now if time is unspecified
            target_dt = ref_time + timedelta(hours=1)

        # Clean content text
        cleaned_text = re.sub(
            r"\b(set|a|the|reminder|to|for|remind|me|mujhe|yaad|dilana|dilao|dena|laga|karo|kal|aaj|subah|shaam|baje|at|in|\d+\s*(?:mins?|hours?))\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if not cleaned_text:
            cleaned_text = "Reminder"

        return ReminderIntentData(
            action=ReminderAction.SET,
            text=cleaned_text,
            target_time=target_dt,
        )

    @classmethod
    def _match_volume(cls, text: str) -> VolumeIntentData | None:
        """Matches volume and audio adjustments."""
        is_volume = any(w in text for w in ["volume", "sound", "awaaz", "mute", "unmute", "audio"])
        if not is_volume:
            return None

        # Check mute / unmute
        if "unmute" in text or "awaaz chalu" in text or "awaaz on" in text:
            return VolumeIntentData(action=VolumeAction.UNMUTE)
        if "mute" in text or "awaaz band" in text or "silent" in text:
            return VolumeIntentData(action=VolumeAction.MUTE)

        # Check explicit volume percentage (e.g. "volume 50", "set volume to 80%")
        pct_match = re.search(r"(?:volume\s+(?:to\s+)?|awaaz\s+)(\d{1,3})\s*%?", text)
        if pct_match:
            val = int(pct_match.group(1))
            val = max(0, min(100, val))
            return VolumeIntentData(action=VolumeAction.SET, level=val)

        # Check volume up / increase / badhao
        if any(w in text for w in ["up", "increase", "raise", "badhao", "tez", "zyada", "badha"]):
            step = 10
            step_match = re.search(r"(\d+)\s*%", text)
            if step_match:
                step = int(step_match.group(1))
            return VolumeIntentData(action=VolumeAction.INCREASE, step=step)

        # Check volume down / decrease / kam karo
        if any(w in text for w in ["down", "decrease", "lower", "kam", "dhimi", "ghatao"]):
            step = 10
            step_match = re.search(r"(\d+)\s*%", text)
            if step_match:
                step = int(step_match.group(1))
            return VolumeIntentData(action=VolumeAction.DECREASE, step=step)

        return None

    @classmethod
    def _match_app_launch(cls, text: str) -> AppLaunchIntentData | None:
        """Matches application opening and closing commands."""
        # Reject if dangerous shell metacharacters are present in query
        if any(c in text for c in [";", "&", "|", "`", "$", "<", ">", "\\", "/"]):
            return None

        # Must contain open/launch/start/kholo/chalao or close/band
        is_open = any(w in text for w in ["open", "launch", "start", "run", "kholo", "chalao", "khol"])
        is_close = any(w in text for w in ["close", "exit", "quit", "band karo", "band kar do", "kill"])

        if not (is_open or is_close):
            return None

        action = AppAction.CLOSE if is_close else AppAction.OPEN

        # Check against known application aliases
        for alias, canonical in cls.APP_ALIASES.items():
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, text):
                return AppLaunchIntentData(
                    action=action,
                    app_name=canonical,
                )

        # Generic app name extraction: "open <app_name>"
        match = re.search(r"(?:open|launch|start|close)\s+([a-zA-Z0-9_\-\.]+)", text)
        if match:
            app_str = match.group(1).lower().strip()
            return AppLaunchIntentData(
                action=action,
                app_name=cls.APP_ALIASES.get(app_str, app_str),
            )

        return None

    @classmethod
    def _match_system_query(cls, text: str) -> SystemQueryIntentData | None:
        """Matches system queries for time, date, battery, and status."""
        # Time query
        if any(w in text for w in ["what time is it", "tell me the time", "current time", "samay kya hai", "kitne baje hain", "kya time hua"]):
            return SystemQueryIntentData(query_type=SystemQueryType.TIME)

        # Date query
        if any(w in text for w in ["what is the date", "today's date", "what day is it", "aaj konsi taareekh", "aaj ki date", "aaj konsa din"]):
            return SystemQueryIntentData(query_type=SystemQueryType.DATE)

        # Battery query
        if any(w in text for w in ["battery", "battery level", "battery status", "charge kitna hai", "battery kitni hai"]):
            return SystemQueryIntentData(query_type=SystemQueryType.BATTERY)

        # Overall status query
        if any(w in text for w in ["system status", "health status", "device status"]):
            return SystemQueryIntentData(query_type=SystemQueryType.STATUS)

        return None
