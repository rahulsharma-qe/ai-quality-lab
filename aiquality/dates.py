"""Days as people write them: 30-11-2026 (DD-MM-YYYY). 2026-11-30 is read too, and is how run records
store a day, so they sort."""

from datetime import date
from typing import Optional

FORMATS = ("%d-%m-%Y", "%Y-%m-%d")


def parse_day(value) -> Optional[date]:
    """A date from 30-11-2026 or 2026-11-30; None when it is neither (or not a real day)."""
    from datetime import datetime
    if isinstance(value, date):
        return value
    for form in FORMATS:
        try:
            return datetime.strptime(str(value).strip(), form).date()
        except ValueError:
            continue
    return None


def shown_day(value) -> str:
    """30-11-2026, from a date or a stored 2026-11-30; anything else as it is."""
    day = parse_day(value)
    return day.strftime("%d-%m-%Y") if day else str(value)


def day_argument(text: str) -> date:
    """For the command line: a clear message when the day can't be read."""
    import argparse
    day = parse_day(text)
    if day is None:
        raise argparse.ArgumentTypeError(f"'{text}' is not a day: write it as 30-11-2026")
    return day
