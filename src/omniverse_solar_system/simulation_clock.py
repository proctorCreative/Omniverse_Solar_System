"""A small, testable simulation clock independent of Omniverse."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic


@dataclass
class SimulationClock:
    """Map monotonic real time to a controllable UTC simulation time.

    ``rate`` is measured in simulated seconds per real second. A rate of zero
    pauses the clock; negative values run it backward.
    """

    anchor_utc: datetime
    anchor_monotonic: float
    rate: float = 0.0

    @classmethod
    def paused_at(
        cls,
        when_utc: datetime | None = None,
        *,
        monotonic_now: float | None = None,
    ) -> "SimulationClock":
        when = when_utc or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        when = when.astimezone(timezone.utc)
        return cls(
            anchor_utc=when,
            anchor_monotonic=monotonic() if monotonic_now is None else monotonic_now,
            rate=0.0,
        )

    @property
    def is_playing(self) -> bool:
        return self.rate != 0.0

    def current(self, *, monotonic_now: float | None = None) -> datetime:
        now_mono = monotonic() if monotonic_now is None else monotonic_now
        elapsed_real_seconds = now_mono - self.anchor_monotonic
        return self.anchor_utc + timedelta(seconds=elapsed_real_seconds * self.rate)

    def set_rate(self, rate: float, *, monotonic_now: float | None = None) -> None:
        now_mono = monotonic() if monotonic_now is None else monotonic_now
        current = self.current(monotonic_now=now_mono)
        self.anchor_utc = current
        self.anchor_monotonic = now_mono
        self.rate = float(rate)

    def pause(self, *, monotonic_now: float | None = None) -> None:
        self.set_rate(0.0, monotonic_now=monotonic_now)

    def reset_to_now(
        self,
        when_utc: datetime | None = None,
        *,
        monotonic_now: float | None = None,
    ) -> None:
        when = when_utc or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        self.anchor_utc = when.astimezone(timezone.utc)
        self.anchor_monotonic = monotonic() if monotonic_now is None else monotonic_now
        self.rate = 0.0


def format_playback_rate(rate: float) -> str:
    """Human-readable simulation speed for the Orrery status panel."""
    value = abs(float(rate))
    sign = "−" if rate < 0.0 else "+"
    if value == 0.0:
        return "paused"
    if value % 86_400.0 == 0.0:
        amount = value / 86_400.0
        unit = "day" if amount == 1.0 else "days"
    elif value % 3_600.0 == 0.0:
        amount = value / 3_600.0
        unit = "hour" if amount == 1.0 else "hours"
    elif value >= 1.0:
        amount = value
        unit = "seconds"
    else:
        amount = value
        unit = "seconds"
    amount_text = f"{amount:g}"
    return f"{sign}{amount_text} {unit}/s"
