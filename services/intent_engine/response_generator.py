"""Bilingual Structured Natural Voice Response Generator.

Produces concise, high-clarity voice output in English, Hindi, and Hinglish
without requiring external LLM token generation.
"""

import logging
from datetime import datetime
from typing import Any

from packages.contracts.deterministic import (
    AlarmAction,
    AppAction,
    ReminderAction,
    SystemQueryType,
    TimerAction,
    VolumeAction,
)
from packages.contracts.intents import IntentPacket
from packages.contracts.tools import ToolExecutionResult

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates structured natural voice responses based on execution outcomes."""

    @classmethod
    def generate_response(
        cls,
        packet: IntentPacket,
        result: ToolExecutionResult,
    ) -> str:
        """Generates voice response string."""
        lang = packet.language.lower() if packet.language else "en"
        is_hindi = lang.startswith("hi") or lang == "hinglish"

        if not result.success:
            return cls._format_error(packet, result, is_hindi)

        target = packet.target_intent
        entities = packet.extracted_entities
        output = result.output or {}

        if target == "TIMER":
            return cls._format_timer_response(entities, output, is_hindi)
        elif target == "ALARM":
            return cls._format_alarm_response(entities, output, is_hindi)
        elif target == "REMINDER":
            return cls._format_reminder_response(entities, output, is_hindi)
        elif target == "VOLUME":
            return cls._format_volume_response(entities, output, is_hindi)
        elif target == "APP_LAUNCH":
            return cls._format_app_response(entities, output, is_hindi)
        elif target == "SYSTEM_QUERY":
            return cls._format_system_query_response(entities, output, is_hindi)

        return "Command completed successfully." if not is_hindi else "Command successfully poora ho gaya hai."

    @classmethod
    def _format_error(cls, packet: IntentPacket, result: ToolExecutionResult, is_hindi: bool) -> str:
        """Formats error and policy rejection messages."""
        err_msg = result.error or "Unknown error"
        if "Security Policy" in err_msg or "denied" in err_msg.lower():
            if is_hindi:
                return "Security policy ke tahat ye action block kar diya gaya hai."
            return "Action blocked by security policy."

        if is_hindi:
            return f"Maaf kijiye, ye command execute nahi ho payi: {err_msg}"
        return f"Sorry, could not complete request: {err_msg}"

    @classmethod
    def _format_timer_response(cls, entities: dict[str, Any], output: dict[str, Any], is_hindi: bool) -> str:
        action = entities.get("action", TimerAction.SET)
        if action == TimerAction.SET:
            sec = entities.get("duration_seconds", 0)
            if sec >= 60:
                mins = sec // 60
                rem_sec = sec % 60
                time_str = f"{mins} minute" if rem_sec == 0 else f"{mins} minute {rem_sec} seconds"
            else:
                time_str = f"{sec} seconds"

            if is_hindi:
                return f"{time_str} ka timer shuru kar diya hai."
            return f"Timer set for {time_str}."

        elif action == TimerAction.CANCEL:
            if is_hindi:
                return "Timer cancel kar diya gaya hai."
            return "Timer has been cancelled."

        elif action == TimerAction.STATUS:
            rem = output.get("remaining_seconds", 0)
            if is_hindi:
                return f"Timer me abhi {rem} seconds bache hain."
            return f"{rem} seconds remaining on timer."

        return "Timer updated."

    @classmethod
    def _format_alarm_response(cls, entities: dict[str, Any], output: dict[str, Any], is_hindi: bool) -> str:
        action = entities.get("action", AlarmAction.SET)
        if action == AlarmAction.SET:
            target_str = entities.get("time_str")
            if not target_str and "target_time" in output:
                try:
                    dt = datetime.fromisoformat(output["target_time"])
                    target_str = dt.strftime("%I:%M %p")
                except Exception:
                    target_str = str(output["target_time"])

            if is_hindi:
                return f"{target_str} ka alarm set kar diya hai."
            return f"Alarm set for {target_str}."

        elif action == AlarmAction.CANCEL:
            if is_hindi:
                return "Alarm cancel kar diya gaya hai."
            return "Alarm has been cancelled."

        elif action == AlarmAction.LIST:
            count = len(output) if isinstance(output, list) else 0
            if is_hindi:
                return f"Aapke {count} active alarms hain."
            return f"You have {count} active alarms scheduled."

        return "Alarm updated."

    @classmethod
    def _format_reminder_response(cls, entities: dict[str, Any], output: dict[str, Any], is_hindi: bool) -> str:
        action = entities.get("action", ReminderAction.SET)
        if action == ReminderAction.SET:
            txt = entities.get("text", "Reminder")
            if is_hindi:
                return f"Reminder set kar diya gaya hai: {txt}."
            return f"Reminder set: '{txt}'."

        elif action == ReminderAction.CANCEL:
            if is_hindi:
                return "Reminder delete kar diya gaya hai."
            return "Reminder has been cancelled."

        elif action == ReminderAction.LIST:
            count = len(output) if isinstance(output, list) else 0
            if is_hindi:
                return f"Aapke {count} reminders hain."
            return f"You have {count} active reminders."

        return "Reminder updated."

    @classmethod
    def _format_volume_response(cls, entities: dict[str, Any], output: Any, is_hindi: bool) -> str:
        action = entities.get("action")
        if action == VolumeAction.SET:
            lvl = entities.get("level", output)
            if is_hindi:
                return f"Volume {lvl} percent par set kar diya hai."
            return f"Volume set to {lvl}%."

        elif action in [VolumeAction.INCREASE, VolumeAction.DECREASE]:
            if is_hindi:
                return f"Volume update kar diya gaya hai: {output}%."
            return f"Volume adjusted to {output}%."

        elif action == VolumeAction.MUTE:
            if is_hindi:
                return "Audio mute kar diya gaya hai."
            return "Audio is now muted."

        elif action == VolumeAction.UNMUTE:
            if is_hindi:
                return "Audio unmute kar diya gaya hai."
            return "Audio is now unmuted."

        return "Volume updated."

    @classmethod
    def _format_app_response(cls, entities: dict[str, Any], output: Any, is_hindi: bool) -> str:
        action = entities.get("action", AppAction.OPEN)
        app_name = str(entities.get("app_name", "Application")).capitalize()

        if action == AppAction.OPEN:
            if is_hindi:
                return f"{app_name} open kiya ja raha hai."
            return f"Opening {app_name}..."
        elif action == AppAction.CLOSE:
            if is_hindi:
                return f"{app_name} band kar diya gaya hai."
            return f"Closing {app_name}."

        return f"{app_name} updated."

    @classmethod
    def _format_system_query_response(cls, entities: dict[str, Any], output: Any, is_hindi: bool) -> str:
        q_type = entities.get("query_type")
        if q_type == SystemQueryType.TIME:
            now = datetime.now()
            time_str = now.strftime("%I:%M %p")
            if is_hindi:
                return f"Abhi samay {time_str} hai."
            return f"The current time is {time_str}."

        elif q_type == SystemQueryType.DATE:
            now = datetime.now()
            date_str = now.strftime("%A, %B %d, %Y")
            if is_hindi:
                return f"Aaj {date_str} hai."
            return f"Today is {date_str}."

        elif q_type == SystemQueryType.BATTERY:
            pct = output.get("percentage", 100) if isinstance(output, dict) else 100
            if is_hindi:
                return f"Battery level {pct} percent hai."
            return f"Battery level is at {pct}%."

        return "System is running normally."
