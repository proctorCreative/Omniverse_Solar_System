import numpy as np

from omniverse_solar_system.catalog import OrbitalCatalog
from omniverse_solar_system.engine import SolarSystemEngine


def _engine_with_h(values):
    engine = SolarSystemEngine.__new__(SolarSystemEngine)
    arrays = {"h": np.asarray(values, dtype=np.float32), "e": np.zeros(len(values))}
    engine.asteroids = OrbitalCatalog(
        name="asteroids",
        arrays=arrays,
        manifest={"count": len(values)},
    )
    engine._asteroid_brightness_order = None
    return engine


def test_playback_subset_prioritizes_bright_finite_h_and_is_stable():
    engine = _engine_with_h([12.0, np.nan, 4.0, 9.0, 4.0])
    first = engine.asteroid_playback_indices(3)
    second = engine.asteroid_playback_indices(3)
    assert first.tolist() == [2, 4, 3]
    assert second.tolist() == first.tolist()


def test_playback_subset_can_be_constrained_to_staged_catalog_prefix():
    engine = _engine_with_h([12.0, 1.0, 4.0, 0.5, 9.0])
    indices = engine.asteroid_playback_indices(3, within_limit=3)
    assert indices.tolist() == [1, 2, 0]
