"""
Shared calendar-month helpers for reporting modules that operate on
monthly windows (CoCM Quality Metrics, Monthly Time Tracker). Kept in one
place so "how to compute a month's start/end" and "how to step N months
from a (year, month) pair" aren't reimplemented slightly differently in
each report — the same "don't hardcode... in more than one place" rule
CLAUDE.md states for clinical thresholds, applied here to date math.

app/services/drr.py has its own, different day-preserving _add_months
(adding N months to a specific *date*, e.g. a baseline_date, clamping the
day-of-month) — that's a distinct operation from stepping whole calendar
months here and is left where it is rather than folded into this module.
"""

from datetime import date, timedelta


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """The first and last calendar day of (year, month)."""
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) - timedelta(days=1) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """(year, month) shifted by delta whole calendar months (may be negative)."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1
