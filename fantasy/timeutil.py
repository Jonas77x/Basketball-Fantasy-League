"""Time zone helpers.

Rules (see CLAUDE.md): store UTC, compute NBA/Yahoo days in US-Eastern, show Europe/Berlin.
Never use fixed offsets – the Berlin/New York gap changes between 5 and 6 hours.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

NBA_TZ = ZoneInfo("America/New_York")
DISPLAY_TZ = ZoneInfo("Europe/Berlin")

WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime – attach a time zone first")
    return dt.astimezone(UTC)


def nba_day(dt: datetime | None = None) -> date:
    """The NBA / Yahoo roster day for a moment in time (date in US-Eastern)."""
    dt = dt or utcnow()
    return to_utc(dt).astimezone(NBA_TZ).date()


def to_display(dt: datetime) -> datetime:
    return to_utc(dt).astimezone(DISPLAY_TZ)


def format_display(dt: datetime, with_weekday: bool = True) -> str:
    """Format a moment for Jonas, e.g. 'Mo 19.10., 21:00'."""
    local = to_display(dt)
    text = local.strftime("%d.%m., %H:%M")
    if with_weekday:
        text = f"{WEEKDAYS_DE[local.weekday()]} {text}"
    return text
