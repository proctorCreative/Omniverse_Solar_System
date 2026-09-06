from dataclasses import dataclass
import numpy as np
import pytest

from omniverse_solar_system.constants import GAUSSIAN_K_RAD_PER_DAY, J2000_JD
from omniverse_solar_system.propagation import propagate_catalog


@dataclass
class FakeCatalog:
    arrays: dict

    def __getitem__(self, key):
        return self.arrays[key]


def catalog(**overrides):
    base = {
        "a": np.array([1.0]),
        "e": np.array([0.0]),
        "inc": np.array([0.0]),
        "node": np.array([0.0]),
        "argp": np.array([0.0]),
        "m0": np.array([0.0]),
        "n": np.array([np.pi / 2.0]),
        "epoch": np.array([2451545.0]),
        "tp": np.array([np.nan]),
        "q": np.array([1.0]),
        "h": np.array([10.0]),
    }
    base.update(overrides)
    return FakeCatalog(base)


def test_circular_orbit_at_epoch():
    positions, mask = propagate_catalog(catalog(), 2451545.0)
    assert mask.tolist() == [True]
    np.testing.assert_allclose(positions[0], [1.0, 0.0, 0.0], atol=1e-12)


def test_circular_quarter_orbit():
    positions, _ = propagate_catalog(catalog(), 2451546.0)
    np.testing.assert_allclose(positions[0], [0.0, 1.0, 0.0], atol=1e-12)


def test_hyperbolic_at_perihelion():
    c = catalog(
        a=np.array([np.nan]),
        e=np.array([1.5]),
        m0=np.array([np.nan]),
        n=np.array([np.nan]),
        epoch=np.array([np.nan]),
        tp=np.array([2451545.0]),
        q=np.array([0.5]),
    )
    positions, _ = propagate_catalog(c, 2451545.0)
    np.testing.assert_allclose(positions[0], [0.5, 0.0, 0.0], atol=1e-12)


def test_parabolic_at_perihelion():
    c = catalog(
        a=np.array([np.nan]),
        e=np.array([1.0]),
        m0=np.array([np.nan]),
        n=np.array([np.nan]),
        epoch=np.array([np.nan]),
        tp=np.array([2451545.0]),
        q=np.array([0.25]),
    )
    positions, _ = propagate_catalog(c, 2451545.0)
    np.testing.assert_allclose(positions[0], [0.25, 0.0, 0.0], atol=1e-12)


def test_limit_zero_returns_empty_catalog():
    positions, mask = propagate_catalog(catalog(), 2451545.0, limit=0)
    assert positions.shape == (0, 3)
    assert mask.shape == (0,)


def test_limit_applies_before_propagation():
    two = catalog(
        a=np.array([1.0, 2.0]),
        e=np.array([0.0, 0.0]),
        inc=np.array([0.0, 0.0]),
        node=np.array([0.0, 0.0]),
        argp=np.array([0.0, 0.0]),
        m0=np.array([0.0, 0.0]),
        n=np.array([0.0, 0.0]),
        epoch=np.array([2451545.0, 2451545.0]),
        tp=np.array([np.nan, np.nan]),
        q=np.array([1.0, 2.0]),
        h=np.array([10.0, 11.0]),
    )
    positions, mask = propagate_catalog(two, 2451545.0, limit=1)
    assert positions.shape == (1, 3)
    assert mask.tolist() == [True]


def test_propagate_catalog_accepts_stable_index_subset():
    selected_catalog = catalog(
        a=np.array([1.0, 4.0, 9.0]),
        e=np.zeros(3),
        inc=np.zeros(3),
        node=np.zeros(3),
        argp=np.zeros(3),
        m0=np.zeros(3),
        n=np.array([GAUSSIAN_K_RAD_PER_DAY, GAUSSIAN_K_RAD_PER_DAY / 8.0, GAUSSIAN_K_RAD_PER_DAY / 27.0]),
        epoch=np.full(3, J2000_JD),
        tp=np.full(3, np.nan),
        q=np.full(3, np.nan),
    )
    positions, finite = propagate_catalog(selected_catalog, J2000_JD, indices=np.array([2, 0]))
    assert finite.tolist() == [True, True]
    assert np.allclose(positions[:, 0], [9.0, 1.0])


def test_propagate_catalog_rejects_limit_and_indices_together():
    selected_catalog = catalog()
    with pytest.raises(ValueError, match="mutually exclusive"):
        propagate_catalog(selected_catalog, J2000_JD, limit=1, indices=np.array([0]))
