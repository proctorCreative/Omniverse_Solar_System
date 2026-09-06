import numpy as np
import pytest

from omniverse_solar_system.orbit_visibility import (
    full_orbit_is_projection_safe,
    orbit_max_radius,
)


def test_orbit_max_radius():
    points = np.array([[0.0, 0.0, 0.0], [3.0, 4.0, 0.0], [-2.0, 0.0, 0.0]])
    assert orbit_max_radius(points) == pytest.approx(5.0)


def test_orbit_max_radius_rejects_bad_shape():
    with pytest.raises(ValueError):
        orbit_max_radius(np.zeros((3, 2)))


def test_full_orbit_safe_only_when_camera_is_outside_with_margin():
    assert full_orbit_is_projection_safe(11.0, 10.0, margin=1.05)
    assert not full_orbit_is_projection_safe(10.4, 10.0, margin=1.05)
    assert not full_orbit_is_projection_safe(5.0, 10.0, margin=1.05)


def test_full_orbit_visibility_rejects_invalid_margin():
    with pytest.raises(ValueError):
        full_orbit_is_projection_safe(10.0, 5.0, margin=0.9)
