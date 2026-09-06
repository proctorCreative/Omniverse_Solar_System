"""Camera-distance rules for robust full-orbit overlay rendering."""

from __future__ import annotations

import numpy as np


def orbit_max_radius(points: np.ndarray) -> float:
    """Return the largest heliocentric distance in an ``(N, 3)`` orbit polyline."""
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("orbit points must have shape (N, 3)")
    if len(array) == 0:
        return 0.0
    return float(np.linalg.norm(array, axis=1).max())


def full_orbit_is_projection_safe(
    camera_distance: float,
    max_orbit_radius: float,
    *,
    margin: float = 1.05,
) -> bool:
    """Whether a complete closed orbit remains in front of an origin-facing camera.

    A camera outside a sphere containing the orbit can see the complete polyline
    without any vertices passing behind the camera plane.  Once the camera moves
    inside that sphere, perspective projection of the closed curve develops
    asymptotic/near-plane artifacts.  ``margin`` hides the curve slightly before
    the exact crossing to avoid flicker.
    """
    camera_distance = float(camera_distance)
    max_orbit_radius = float(max_orbit_radius)
    margin = float(margin)
    if not np.isfinite(camera_distance) or camera_distance < 0.0:
        return False
    if not np.isfinite(max_orbit_radius) or max_orbit_radius < 0.0:
        return False
    if not np.isfinite(margin) or margin < 1.0:
        raise ValueError("margin must be finite and at least 1.0")
    return camera_distance > max_orbit_radius * margin
