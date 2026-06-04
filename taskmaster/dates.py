from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Optional

try:
    import dateparser  # type: ignore

    _HAS_DATEPARSER = True
except ImportError:  # pragma: no cover - environment-dependent
    _HAS_DATEPARSER = False


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_NEXT_WEEKDAY_RE = re.compile(
    r"^next\s+(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b(.*)$", re.IGNORECASE
)


def expand_next_weekday(text: str, base: datetime) -> str:
    match = _NEXT_WEEKDAY_RE.match(text.strip())
    if not match:
        return text
    abbrev, remainder = match.group(1).lower(), match.group(2).strip()
    target = next(i for name, i in _WEEKDAYS.items() if name.startswith(abbrev))
    # Days until the *next* occurrence (always at least 1, up to 7).
    delta = (target - base.weekday() + 7) % 7
    delta = delta or 7
    date = base + timedelta(days=delta)
    rebuilt = date.strftime("%Y-%m-%d")
    return f"{rebuilt} {remainder}".strip() if remainder else rebuilt


_STRICT_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
)


def parse_due(raw: str) -> Optional[datetime]:
    text = (raw or "").strip()
    if not text:
        return None

    if _HAS_DATEPARSER:
        prepared = expand_next_weekday(text, datetime.now())
        parsed = dateparser.parse(
            prepared,
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )
        if parsed is not None:
            return parsed

    for fmt in _STRICT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    hint = (
        "tomorrow 5pm" if _HAS_DATEPARSER else "YYYY-MM-DD HH:MM"
    )
    raise ValueError(f"Could not understand the date '{text}'. Try e.g. '{hint}'.")


def format_due(due: Optional[datetime]) -> str:
    if due is None:
        return "—"
    return due.strftime("%Y-%m-%d %H:%M")
