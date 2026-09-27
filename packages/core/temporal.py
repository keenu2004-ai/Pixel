"""Bilingual Hindi/Hinglish/English Temporal Intent Resolver.

Parses natural temporal expressions to normalized datetime objects without external cloud dependencies.
"""

import re
from datetime import datetime, timedelta


class TemporalResolver:
    """Resolves relative date and time expressions across English, Hindi, and Hinglish."""

    # Hindi/Hinglish relative day offsets
    DAY_OFFSETS: dict[str, int] = {
        "aaj": 0,
        "today": 0,
        "kal": 1,         # tomorrow
        "tomorrow": 1,
        "parso": 2,       # day after tomorrow
        "narso": 3,
    }

    # Time of day default fallback hours
    TIME_OF_DAY_DEFAULTS: dict[str, tuple[int, int]] = {
        "subah": (7, 0),     # Morning default: 7:00 AM
        "morning": (7, 0),
        "dopahar": (13, 0),  # Afternoon default: 1:00 PM
        "afternoon": (13, 0),
        "shaam": (18, 0),    # Evening default: 6:00 PM
        "evening": (18, 0),
        "raat": (21, 0),     # Night default: 9:00 PM
        "night": (21, 0),
    }

    WEEKDAYS: dict[str, int] = {
        "somwar": 0, "monday": 0,
        "mangalwar": 1, "tuesday": 1,
        "budhwar": 2, "wednesday": 2,
        "guruwar": 3, "brihaspatiwar": 3, "thursday": 3,
        "shukrawar": 4, "friday": 4,
        "shaniwar": 5, "saturday": 5,
        "raviwar": 6, "itwar": 6, "sunday": 6,
    }

    @classmethod
    def resolve_datetime(
        cls,
        text: str,
        reference_time: datetime | None = None
    ) -> datetime | None:
        """Parses an utterance and returns the normalized datetime."""
        base_time = reference_time or datetime.now()
        normalized = text.lower().strip()

        # Check 1: "in X minutes / in X hours" / "X minute baad"
        rel_min_match = re.search(r"(?:in\s+)?(\d+)\s*(?:mins?|minutes?|minute)\s*(?:baad|me|mein)?", normalized)
        if rel_min_match:
            mins = int(rel_min_match.group(1))
            return base_time + timedelta(minutes=mins)

        rel_hr_match = re.search(r"(?:in\s+)?(\d+)\s*(?:hours?|hrs?|ghante)\s*(?:baad|me|mein)?", normalized)
        if rel_hr_match:
            hrs = int(rel_hr_match.group(1))
            return base_time + timedelta(hours=hrs)

        # Check 2: Relative day offset (aaj, kal, parso, tomorrow, etc.)
        target_date = base_time.date()
        day_offset_found = False
        for day_word, offset in cls.DAY_OFFSETS.items():
            pattern = rf"\b{day_word}\b"
            if re.search(pattern, normalized):
                target_date = base_time.date() + timedelta(days=offset)
                day_offset_found = True
                break

        # Check 3: Next weekday ("agla somwar", "next monday")
        for weekday_word, weekday_idx in cls.WEEKDAYS.items():
            pattern = rf"\b(?:next|agla|agle)\s+{weekday_word}\b|\b{weekday_word}\b"
            if re.search(pattern, normalized) and not day_offset_found:
                current_weekday = base_time.weekday()
                days_ahead = (weekday_idx - current_weekday) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = base_time.date() + timedelta(days=days_ahead)
                day_offset_found = True
                break

        # Check 4: Exact hour & minute ("7 baje", "7:30", "7 am", "subah 7 baje", "shaam 6 baje")
        time_match = re.search(
            r"(?:(subah|shaam|dopahar|raat|morning|evening|night)\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje)?",
            normalized
        )

        if time_match:
            period = time_match.group(1)
            hour = int(time_match.group(2))
            minute = int(time_match.group(3)) if time_match.group(3) else 0
            meridiem = time_match.group(4)

            # Adjust for 12-hour clock and Hindi time periods
            if meridiem == "pm" or period in ["shaam", "raat", "dopahar", "evening", "night"]:
                if hour < 12:
                    hour += 12
            elif meridiem == "am" or period in ["subah", "morning"]:
                if hour == 12:
                    hour = 0

            return datetime.combine(target_date, datetime.min.time()).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

        # Check 5: Only period mentioned without exact hour (e.g. "aaj shaam", "kal subah")
        for period_word, (def_hr, def_min) in cls.TIME_OF_DAY_DEFAULTS.items():
            if re.search(rf"\b{period_word}\b", normalized) and day_offset_found:
                return datetime.combine(target_date, datetime.min.time()).replace(
                    hour=def_hr, minute=def_min, second=0, microsecond=0
                )

        return None
