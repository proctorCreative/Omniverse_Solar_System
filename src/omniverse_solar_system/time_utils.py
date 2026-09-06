"""Small, dependency-free Julian-date helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def calendar_to_jd(year: int, month: int, day: float) -> float:
    """Convert a proleptic Gregorian calendar date to Julian Date.

    ``day`` may include a fractional day.
    """
    y = int(year)
    m = int(month)
    d = float(day)
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return (
        int(365.25 * (y + 4716))
        + int(30.6001 * (m + 1))
        + d
        + b
        - 1524.5
    )


def datetime_to_jd(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    day_fraction = (
        value.hour
        + value.minute / 60.0
        + (value.second + value.microsecond / 1_000_000.0) / 3600.0
    ) / 24.0
    return calendar_to_jd(value.year, value.month, value.day + day_fraction)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_jd() -> float:
    return datetime_to_jd(utc_now())
