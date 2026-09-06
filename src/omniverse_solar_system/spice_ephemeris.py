"""J2000 planet positions and orbit guides from the supplied DE440 SPK."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .constants import AU_KM, PLANET_TARGETS, SECONDS_PER_DAY


class SpiceEphemeris:
    def __init__(self, de440_path: Path, leap_seconds_path: Path) -> None:
        try:
            import spiceypy as spice
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "spiceypy is unavailable. Run scripts/install_kit_dependencies.sh "
                "with your Kit python launcher."
            ) from exc
        self.spice = spice
        self.de440_path = Path(de440_path)
        self.leap_seconds_path = Path(leap_seconds_path)
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        for path in (self.leap_seconds_path, self.de440_path):
            if not path.exists():
                raise FileNotFoundError(path)
            self.spice.furnsh(str(path))
        self._loaded = True

    def close(self) -> None:
        if self._loaded:
            self.spice.kclear()
            self._loaded = False

    @staticmethod
    def _format_utc(when: datetime) -> str:
        """Return a CSPICE-compatible ISO-8601 UTC string.

        CSPICE accepts the ISO ``T`` form with a trailing ``Z``. Appending a
        separate `` UTC`` token to a string containing ``T`` is not one of the
        accepted ISO token patterns and raises SPICE(UNPARSEDTIME).
        """
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        when = when.astimezone(timezone.utc)
        return when.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def _et(self, when: datetime) -> float:
        return float(self.spice.str2et(self._format_utc(when)))

    def planet_positions(self, when: datetime) -> tuple[list[str], np.ndarray]:
        self.load()
        et = self._et(when)
        positions = []
        names = []
        for display_name, target_name, _period_days in PLANET_TARGETS:
            pos_km, _lt = self.spice.spkpos(
                target_name, et, "J2000", "NONE", "SUN"
            )
            names.append(display_name)
            positions.append(np.asarray(pos_km, dtype=np.float64) / AU_KM)
        return names, np.asarray(positions, dtype=np.float64)

    def orbit_lines(
        self, when: datetime, samples: int = 384
    ) -> dict[str, np.ndarray]:
        self.load()
        et0 = self._et(when)
        lines: dict[str, np.ndarray] = {}
        for display_name, target_name, period_days in PLANET_TARGETS:
            ets = et0 + np.linspace(
                0.0, period_days * SECONDS_PER_DAY, int(samples), endpoint=False
            )
            pos_km, _lt = self.spice.spkpos(
                target_name, ets, "J2000", "NONE", "SUN"
            )
            points = np.asarray(pos_km, dtype=np.float64) / AU_KM
            points = np.vstack((points, points[0]))
            lines[display_name] = points
        return lines
