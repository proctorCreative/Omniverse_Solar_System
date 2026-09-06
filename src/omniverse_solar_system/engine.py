"""High-level scientific engine with no Omniverse dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .catalog import OrbitalCatalog, load_catalog
from .frames import ecliptic_j2000_to_equatorial_j2000
from .gpu_catalog import PackedGpuAsteroids, pack_gpu_asteroids
from .paths import resolve_project_paths
from .propagation import propagate_catalog
from .spice_ephemeris import SpiceEphemeris
from .time_utils import datetime_to_jd


@dataclass(frozen=True)
class PositionSnapshot:
    when_utc: datetime
    jd_utc: float
    planet_names: list[str]
    planet_positions: np.ndarray
    asteroid_positions: np.ndarray
    coordinate_frame: str = "J2000"


class SolarSystemEngine:
    def __init__(
        self,
        project_root: Path,
        *,
        raw_data_root: Path | None = None,
        cache_root: Path | None = None,
    ) -> None:
        paths = resolve_project_paths(
            project_root, raw_data_root=raw_data_root, cache_root=cache_root
        )
        self.project_root = paths.project_root
        self.raw_data_root = paths.raw_data_root
        self.cache_root = paths.cache_root
        raw = self.raw_data_root
        self.asteroids: OrbitalCatalog = load_catalog(self.cache_root, "asteroids")
        self.spice = SpiceEphemeris(
            raw / "spice" / "de440.bsp",
            raw / "spice" / "naif0012.tls",
        )
        self._asteroid_brightness_order: np.ndarray | None = None

    def close(self) -> None:
        self.spice.close()

    @staticmethod
    def _normalize_time(when: datetime | None) -> datetime:
        when = when or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return when.astimezone(timezone.utc)

    def compute_snapshot(
        self,
        when: datetime | None = None,
        asteroid_limit: int | None = None,
        asteroid_indices: np.ndarray | None = None,
    ) -> PositionSnapshot:
        """Compute planets plus a CPU-propagated asteroid population.

        This remains the scientific reference and automatic fallback path. The
        v2 GPU renderer uses :meth:`compute_primary_snapshot` and keeps asteroid
        orbital elements resident on the GPU.
        """
        when = self._normalize_time(when)
        jd = datetime_to_jd(when)

        # DE440 is requested directly in equatorial J2000/ICRF.
        planet_names, planet_positions = self.spice.planet_positions(when)

        # MPC elements are propagated in heliocentric ECLIPJ2000, then rotated
        # once at the rendering boundary so all displayed data shares one frame:
        # +Z NCP, +X vernal equinox, +Y RA 6h.
        asteroid_ecliptic, _asteroid_mask = propagate_catalog(
            self.asteroids,
            jd,
            limit=asteroid_limit if asteroid_indices is None else None,
            indices=asteroid_indices,
        )
        asteroid_positions = ecliptic_j2000_to_equatorial_j2000(asteroid_ecliptic)

        return PositionSnapshot(
            when_utc=when,
            jd_utc=jd,
            planet_names=planet_names,
            planet_positions=np.ascontiguousarray(planet_positions, dtype=np.float32),
            asteroid_positions=np.ascontiguousarray(
                asteroid_positions, dtype=np.float32
            ),
        )

    def asteroid_playback_indices(
        self, count: int, within_limit: int | None = None
    ) -> np.ndarray:
        """Return a stable brightness-prioritized asteroid subset.

        Absolute magnitude ``H`` is used when available. The result is cached and
        remains in the same order on every playback frame, preventing flicker.
        ``within_limit`` constrains the candidates for staged modes such as 100k.
        """
        count = max(0, int(count))
        if self._asteroid_brightness_order is None:
            h = np.asarray(self.asteroids["h"], dtype=np.float32)
            sortable = np.where(np.isfinite(h), h, np.inf)
            self._asteroid_brightness_order = np.argsort(sortable, kind="stable")

        order = self._asteroid_brightness_order
        if within_limit is not None:
            candidate_limit = max(0, min(int(within_limit), self.asteroids.count))
            order = order[order < candidate_limit]
        return np.ascontiguousarray(order[:count], dtype=np.intp)

    def compute_primary_snapshot(
        self,
        when: datetime | None = None,
    ) -> PositionSnapshot:
        """Compute only the Sun-relative primary bodies.

        Asteroids remain GPU-resident and are updated by the Warp/Fabric path.
        """
        when = self._normalize_time(when)
        jd = datetime_to_jd(when)
        planet_names, planet_positions = self.spice.planet_positions(when)
        return PositionSnapshot(
            when_utc=when,
            jd_utc=jd,
            planet_names=planet_names,
            planet_positions=np.ascontiguousarray(planet_positions, dtype=np.float32),
            asteroid_positions=np.empty((0, 3), dtype=np.float32),
        )

    def pack_gpu_asteroids(self, count: int | None) -> PackedGpuAsteroids:
        """Pack a brightness-prioritized population for one GPU upload."""
        requested = self.asteroids.count if count is None else max(0, int(count))
        requested = min(requested, self.asteroids.count)
        indices = self.asteroid_playback_indices(requested)
        return pack_gpu_asteroids(self.asteroids, indices)

    def compute_orbit_lines(
        self, when: datetime | None = None, samples: int = 1024
    ) -> dict[str, np.ndarray]:
        when = when or datetime.now(timezone.utc)
        lines = self.spice.orbit_lines(when, samples=samples)
        return {
            name: np.ascontiguousarray(points, dtype=np.float32)
            for name, points in lines.items()
        }
