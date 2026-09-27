"""Bilingual Hindi/Hinglish/English Temporal Intent Resolver."""

import re
from datetime import datetime, timedelta


class TemporalResolver:
    """Resolves relative date and time expressions across English, Hindi, and Hinglish."""

    # Hindi/Hinglish relative day mappings
    DAY_OFFSETS: dict[str, int] = {
        "aaj": 0,
        "today": 0,
        "kal": 1,         # tomorrow
        "tomorrow": 1,
        "parso": 2,       # day after tomorrow
        "narso": 3,
    }

    # Time of day keywords (Hindi & English)
    TIME_OF_DAY_DEFAULTS: dict[str, tuple[int, int]] = {
        "subah": (7, 0),     # Morning: default 7:00 AM
        "morning": (7, 0),
        "dopahar": (13, 0),  # Afternoon: default 1:00 PM
        "afternoon": (13, 0),
        "shaam": (18, 0),    # Evening: default 6:00 PM
        "evening": (18, 0),
        "raat": (21, 0),     # Night: default 9:00 PM
        "night": (21, 0),
    }

    @classmethod
    def resolve_datetime(
        cls,
        text: str,
        reference_time: datetime | None = None
    ) -> datetime | None:
        """Parses an utterance and returns the target normalized datetime."""
        base_time = reference_time or datetime.now()
        normalized = text.lower().strip()

        # Step 1: Detect day offset (kal, parso, tomorrow, etc.)
        target_date = base_time.date()
        for day_word, offset in cls.DAY_OFFSETS.items():
            pattern = rf"\b{day_word}\b"
            if re.search(pattern, normalized):
                target_date = base_time.date() + timedelta(days=offset)
                break

        # Step 2: Detect exact hour/minute ("7 baje", "7:30", "7 am", "subah 7 baje")
        # Pattern: (subah/shaam/raat)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje)?
        time_match = re.search(
            r"(?:(subah|shaam|dopahar|raat)\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje)?",
            normalized
        )

        if time_match:
            period = time_match.group(1)
            hour = int(time_match.group(2))
            minute = int(time_match.group(3)) if time_match.group(3) else 0
            meridiem = time_match.group(4)

            # Adjust for 12-hour clock and Hindi periods
            if meridiem == "pm" or period in ["shaam", "raat", "dopahar"]:
                if hour < 12:
                    hour += 12
            elif meridiem == "am" or period in ["subah"]:
                if hour == 12:
                    hour = 0

            return datetime.combine(target_date, datetime.min.time()).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

        return None
