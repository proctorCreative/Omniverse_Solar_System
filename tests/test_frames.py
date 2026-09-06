import numpy as np

from omniverse_solar_system.constants import J2000_MEAN_OBLIQUITY_RAD
from omniverse_solar_system.frames import (
    ecliptic_j2000_to_equatorial_j2000,
    ecliptic_north_in_equatorial_j2000,
    ecliptic_y_in_equatorial_j2000,
)


def test_vernal_equinox_x_axis_is_shared() -> None:
    result = ecliptic_j2000_to_equatorial_j2000(np.array([1.0, 0.0, 0.0]))
    assert np.allclose(result, [1.0, 0.0, 0.0])


def test_ecliptic_y_rotates_toward_positive_celestial_z() -> None:
    result = ecliptic_y_in_equatorial_j2000()
    assert np.allclose(
        result,
        [0.0, np.cos(J2000_MEAN_OBLIQUITY_RAD), np.sin(J2000_MEAN_OBLIQUITY_RAD)],
    )


def test_ecliptic_north_has_negative_equatorial_y() -> None:
    result = ecliptic_north_in_equatorial_j2000()
    assert np.allclose(
        result,
        [0.0, -np.sin(J2000_MEAN_OBLIQUITY_RAD), np.cos(J2000_MEAN_OBLIQUITY_RAD)],
    )


def test_frame_rotation_preserves_vector_lengths() -> None:
    vectors = np.array([[1.0, 2.0, 3.0], [-4.0, 5.0, -6.0]])
    rotated = ecliptic_j2000_to_equatorial_j2000(vectors)
    assert np.allclose(np.linalg.norm(rotated, axis=1), np.linalg.norm(vectors, axis=1))


def test_frame_transform_rejects_non_xyz_input() -> None:
    try:
        ecliptic_j2000_to_equatorial_j2000(np.zeros((4, 2)))
    except ValueError as exc:
        assert "length 3" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
