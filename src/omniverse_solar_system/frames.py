"""Reference-frame transforms used at the scientific/rendering boundary."""

from __future__ import annotations

import numpy as np

from .constants import J2000_MEAN_OBLIQUITY_RAD


def ecliptic_j2000_to_equatorial_j2000(positions: np.ndarray) -> np.ndarray:
    """Rotate heliocentric ECLIPJ2000 vectors into equatorial J2000/ICRF.

    The two frames share the +X axis, which points toward the J2000 vernal
    equinox. The rotation is +epsilon about +X, placing the north celestial
    pole on +Z in the returned coordinates.
    """
    source = np.asarray(positions, dtype=np.float64)
    if source.ndim == 0 or source.shape[-1] != 3:
        raise ValueError("positions must have a final dimension of length 3")

    cosine = np.cos(J2000_MEAN_OBLIQUITY_RAD)
    sine = np.sin(J2000_MEAN_OBLIQUITY_RAD)

    result = np.empty_like(source, dtype=np.float64)
    result[..., 0] = source[..., 0]
    result[..., 1] = cosine * source[..., 1] - sine * source[..., 2]
    result[..., 2] = sine * source[..., 1] + cosine * source[..., 2]
    return result


def ecliptic_north_in_equatorial_j2000() -> np.ndarray:
    """Return the ECLIPJ2000 north-pole unit vector expressed in J2000."""
    return ecliptic_j2000_to_equatorial_j2000(
        np.asarray([0.0, 0.0, 1.0], dtype=np.float64)
    )


def ecliptic_y_in_equatorial_j2000() -> np.ndarray:
    """Return the ECLIPJ2000 +Y unit vector expressed in J2000."""
    return ecliptic_j2000_to_equatorial_j2000(
        np.asarray([0.0, 1.0, 0.0], dtype=np.float64)
    )
