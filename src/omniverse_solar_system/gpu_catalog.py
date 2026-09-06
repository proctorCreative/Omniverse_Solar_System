"""Packing helpers for the GPU-resident asteroid renderer.

The GPU path stores the slowly-changing orbital elements once and updates only a
single simulation-time scalar during playback.  Perifocal orientation vectors are
precomputed in equatorial J2000 so the Warp kernel does no node/inclination/
argument-of-perihelion trigonometry per frame.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .catalog import OrbitalCatalog
from .constants import GAUSSIAN_K_RAD_PER_DAY, J2000_MEAN_OBLIQUITY_RAD


@dataclass(frozen=True)
class PackedGpuAsteroids:
    """Contiguous float32 arrays uploaded once to Fabric/GPU."""

    source_indices: np.ndarray
    semi_major_axis: np.ndarray
    eccentricity: np.ndarray
    mean_anomaly_epoch: np.ndarray
    mean_motion: np.ndarray
    epoch_jd: np.ndarray
    basis_p_j2000: np.ndarray
    basis_q_j2000: np.ndarray
    max_apoapsis_au: float

    @property
    def count(self) -> int:
        return int(self.semi_major_axis.shape[0])

    @property
    def bytes(self) -> int:
        arrays = (
            self.source_indices,
            self.semi_major_axis,
            self.eccentricity,
            self.mean_anomaly_epoch,
            self.mean_motion,
            self.epoch_jd,
            self.basis_p_j2000,
            self.basis_q_j2000,
        )
        return int(sum(array.nbytes for array in arrays))


def _valid_elliptic_mask(catalog: OrbitalCatalog) -> np.ndarray:
    a = np.asarray(catalog["a"])
    e = np.asarray(catalog["e"])
    m0 = np.asarray(catalog["m0"])
    epoch = np.asarray(catalog["epoch"])
    inc = np.asarray(catalog["inc"])
    node = np.asarray(catalog["node"])
    argp = np.asarray(catalog["argp"])
    return (
        np.isfinite(a)
        & (a > 0.0)
        & np.isfinite(e)
        & (e >= 0.0)
        & (e < 1.0)
        & np.isfinite(m0)
        & np.isfinite(epoch)
        & np.isfinite(inc)
        & np.isfinite(node)
        & np.isfinite(argp)
    )


def _orientation_basis_j2000(
    inc: np.ndarray,
    node: np.ndarray,
    argp: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the two perifocal basis vectors in equatorial J2000."""
    cos_o = np.cos(node)
    sin_o = np.sin(node)
    cos_w = np.cos(argp)
    sin_w = np.sin(argp)
    cos_i = np.cos(inc)
    sin_i = np.sin(inc)

    p_ecl = np.column_stack(
        (
            cos_o * cos_w - sin_o * sin_w * cos_i,
            sin_o * cos_w + cos_o * sin_w * cos_i,
            sin_w * sin_i,
        )
    )
    q_ecl = np.column_stack(
        (
            -cos_o * sin_w - sin_o * cos_w * cos_i,
            -sin_o * sin_w + cos_o * cos_w * cos_i,
            cos_w * sin_i,
        )
    )

    cosine = np.cos(J2000_MEAN_OBLIQUITY_RAD)
    sine = np.sin(J2000_MEAN_OBLIQUITY_RAD)

    def rotate(values: np.ndarray) -> np.ndarray:
        result = np.empty_like(values)
        result[:, 0] = values[:, 0]
        result[:, 1] = cosine * values[:, 1] - sine * values[:, 2]
        result[:, 2] = sine * values[:, 1] + cosine * values[:, 2]
        return result

    return rotate(p_ecl), rotate(q_ecl)


def pack_gpu_asteroids(
    catalog: OrbitalCatalog,
    indices: np.ndarray,
) -> PackedGpuAsteroids:
    """Pack a stable selection of usable elliptical asteroid elements.

    Invalid/non-elliptical records are removed while preserving the supplied
    priority order. MPCORB is overwhelmingly elliptical; non-elliptical records
    are excluded from the GPU-resident population.
    """
    requested = np.asarray(indices, dtype=np.intp)
    if requested.ndim != 1:
        raise ValueError("indices must be one-dimensional")
    if requested.size and (requested.min() < 0 or requested.max() >= catalog.count):
        raise IndexError("asteroid index is outside the catalog")

    valid = _valid_elliptic_mask(catalog)
    selected = requested[valid[requested]]

    a64 = np.asarray(catalog["a"][selected], dtype=np.float64)
    e64 = np.asarray(catalog["e"][selected], dtype=np.float64)
    m064 = np.asarray(catalog["m0"][selected], dtype=np.float64)
    n64 = np.asarray(catalog["n"][selected], dtype=np.float64)
    epoch64 = np.asarray(catalog["epoch"][selected], dtype=np.float64)
    inc64 = np.asarray(catalog["inc"][selected], dtype=np.float64)
    node64 = np.asarray(catalog["node"][selected], dtype=np.float64)
    argp64 = np.asarray(catalog["argp"][selected], dtype=np.float64)

    fallback_n = GAUSSIAN_K_RAD_PER_DAY / np.power(a64, 1.5)
    n64 = np.where(np.isfinite(n64) & (n64 > 0.0), n64, fallback_n)
    p64, q64 = _orientation_basis_j2000(inc64, node64, argp64)

    apoapsis = a64 * (1.0 + e64)
    max_apoapsis = float(np.nanmax(apoapsis, initial=0.0))

    return PackedGpuAsteroids(
        source_indices=np.ascontiguousarray(selected, dtype=np.int32),
        semi_major_axis=np.ascontiguousarray(a64, dtype=np.float32),
        eccentricity=np.ascontiguousarray(e64, dtype=np.float32),
        mean_anomaly_epoch=np.ascontiguousarray(m064, dtype=np.float32),
        mean_motion=np.ascontiguousarray(n64, dtype=np.float32),
        epoch_jd=np.ascontiguousarray(epoch64, dtype=np.float32),
        basis_p_j2000=np.ascontiguousarray(p64, dtype=np.float32),
        basis_q_j2000=np.ascontiguousarray(q64, dtype=np.float32),
        max_apoapsis_au=max_apoapsis,
    )


def evaluate_packed_cpu(packed: PackedGpuAsteroids, jd: float) -> np.ndarray:
    """Reference implementation matching the fixed-iteration GPU kernel."""
    a = packed.semi_major_axis.astype(np.float64)
    e = packed.eccentricity.astype(np.float64)
    m = packed.mean_anomaly_epoch.astype(np.float64) + packed.mean_motion.astype(
        np.float64
    ) * (float(jd) - packed.epoch_jd.astype(np.float64))
    m = (m + np.pi) % (2.0 * np.pi) - np.pi
    estimate = np.where(e < 0.8, m, m + np.sign(np.sin(m)) * 0.85 * e)
    for _ in range(12):
        estimate -= (estimate - e * np.sin(estimate) - m) / (
            1.0 - e * np.cos(estimate)
        )
    x_pf = a * (np.cos(estimate) - e)
    y_pf = a * np.sqrt(np.maximum(0.0, 1.0 - e * e)) * np.sin(estimate)
    result = (
        packed.basis_p_j2000.astype(np.float64) * x_pf[:, None]
        + packed.basis_q_j2000.astype(np.float64) * y_pf[:, None]
    )
    return np.ascontiguousarray(result, dtype=np.float32)
