"""Vectorized two-body propagation in heliocentric ecliptic J2000 coordinates."""

from __future__ import annotations

import numpy as np

from .constants import GAUSSIAN_K_RAD_PER_DAY
from .catalog import OrbitalCatalog


def _solve_elliptic_kepler(mean_anomaly: np.ndarray, eccentricity: np.ndarray) -> np.ndarray:
    m = (mean_anomaly + np.pi) % (2.0 * np.pi) - np.pi
    e = eccentricity
    estimate = m + np.sign(np.sin(m)) * 0.85 * e
    estimate = np.where(e < 0.8, m, estimate)
    for _ in range(12):
        f = estimate - e * np.sin(estimate) - m
        fp = 1.0 - e * np.cos(estimate)
        delta = f / fp
        estimate -= delta
        if np.nanmax(np.abs(delta), initial=0.0) < 1.0e-12:
            break
    return estimate


def _solve_hyperbolic_kepler(mean_anomaly: np.ndarray, eccentricity: np.ndarray) -> np.ndarray:
    h = np.arcsinh(mean_anomaly / np.maximum(eccentricity, 1.0000001))
    for _ in range(16):
        f = eccentricity * np.sinh(h) - h - mean_anomaly
        fp = eccentricity * np.cosh(h) - 1.0
        delta = f / fp
        h -= delta
        if np.nanmax(np.abs(delta), initial=0.0) < 1.0e-12:
            break
    return h


def _rotate_perifocal(
    x_pf: np.ndarray,
    y_pf: np.ndarray,
    inc: np.ndarray,
    node: np.ndarray,
    argp: np.ndarray,
) -> np.ndarray:
    cos_o = np.cos(node)
    sin_o = np.sin(node)
    cos_w = np.cos(argp)
    sin_w = np.sin(argp)
    cos_i = np.cos(inc)
    sin_i = np.sin(inc)

    p_x = cos_o * cos_w - sin_o * sin_w * cos_i
    p_y = sin_o * cos_w + cos_o * sin_w * cos_i
    p_z = sin_w * sin_i
    q_x = -cos_o * sin_w - sin_o * cos_w * cos_i
    q_y = -sin_o * sin_w + cos_o * cos_w * cos_i
    q_z = cos_w * sin_i

    return np.column_stack(
        (
            p_x * x_pf + q_x * y_pf,
            p_y * x_pf + q_y * y_pf,
            p_z * x_pf + q_z * y_pf,
        )
    )


def propagate_catalog(
    catalog: OrbitalCatalog,
    jd: float,
    *,
    limit: int | None = None,
    indices: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Propagate all usable catalog records to ``jd``.

    Returns a compact ``(N, 3)`` float64 position array and a boolean mask into the
    original cache. Elliptical records use MPC's supplied mean daily motion. Records
    with non-elliptical eccentricity use perihelion time and distance when available.
    """
    if limit is not None and indices is not None:
        raise ValueError("limit and indices are mutually exclusive")
    if indices is not None:
        selection = np.asarray(indices, dtype=np.intp)
        if selection.ndim != 1:
            raise ValueError("indices must be a one-dimensional array")
    elif limit is None:
        selection = slice(None)
    else:
        limit = max(0, int(limit))
        selection = slice(0, limit)

    a = np.asarray(catalog["a"][selection], dtype=np.float64)
    e = np.asarray(catalog["e"][selection], dtype=np.float64)
    inc = np.asarray(catalog["inc"][selection], dtype=np.float64)
    node = np.asarray(catalog["node"][selection], dtype=np.float64)
    argp = np.asarray(catalog["argp"][selection], dtype=np.float64)
    m0 = np.asarray(catalog["m0"][selection], dtype=np.float64)
    n = np.asarray(catalog["n"][selection], dtype=np.float64)
    epoch = np.asarray(catalog["epoch"][selection], dtype=np.float64)
    tp = np.asarray(catalog["tp"][selection], dtype=np.float64)
    q = np.asarray(catalog["q"][selection], dtype=np.float64)

    total = e.shape[0]
    positions = np.full((total, 3), np.nan, dtype=np.float64)

    ellipse = (
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
    if np.any(ellipse):
        ae = a[ellipse]
        ee = e[ellipse]
        ne = n[ellipse]
        fallback_n = GAUSSIAN_K_RAD_PER_DAY / np.power(ae, 1.5)
        ne = np.where(np.isfinite(ne) & (ne > 0.0), ne, fallback_n)
        mean = m0[ellipse] + ne * (jd - epoch[ellipse])
        ecc_anomaly = _solve_elliptic_kepler(mean, ee)
        x_pf = ae * (np.cos(ecc_anomaly) - ee)
        y_pf = ae * np.sqrt(np.maximum(0.0, 1.0 - ee * ee)) * np.sin(ecc_anomaly)
        positions[ellipse] = _rotate_perifocal(
            x_pf, y_pf, inc[ellipse], node[ellipse], argp[ellipse]
        )

    conic = (
        ~ellipse
        & np.isfinite(e)
        & (e >= 0.0)
        & np.isfinite(q)
        & (q > 0.0)
        & np.isfinite(tp)
        & np.isfinite(inc)
        & np.isfinite(node)
        & np.isfinite(argp)
    )
    if np.any(conic):
        ec = e[conic]
        qc = q[conic]
        dt = jd - tp[conic]
        x_pf = np.full(ec.shape, np.nan, dtype=np.float64)
        y_pf = np.full(ec.shape, np.nan, dtype=np.float64)

        near_parabolic = np.abs(ec - 1.0) <= 1.0e-5
        elliptical = ec < (1.0 - 1.0e-5)
        hyperbolic = ec > (1.0 + 1.0e-5)

        if np.any(elliptical):
            qv = qc[elliptical]
            ev = ec[elliptical]
            av = qv / (1.0 - ev)
            mean = GAUSSIAN_K_RAD_PER_DAY * dt[elliptical] / np.power(av, 1.5)
            eccentric_anomaly = _solve_elliptic_kepler(mean, ev)
            x_pf[elliptical] = av * (np.cos(eccentric_anomaly) - ev)
            y_pf[elliptical] = (
                av
                * np.sqrt(np.maximum(0.0, 1.0 - ev * ev))
                * np.sin(eccentric_anomaly)
            )

        if np.any(hyperbolic):
            qv = qc[hyperbolic]
            ev = ec[hyperbolic]
            av = qv / (ev - 1.0)
            mean = GAUSSIAN_K_RAD_PER_DAY * dt[hyperbolic] / np.power(av, 1.5)
            hyperbolic_anomaly = _solve_hyperbolic_kepler(mean, ev)
            x_pf[hyperbolic] = av * (ev - np.cosh(hyperbolic_anomaly))
            y_pf[hyperbolic] = (
                av
                * np.sqrt(np.maximum(0.0, ev * ev - 1.0))
                * np.sinh(hyperbolic_anomaly)
            )

        if np.any(near_parabolic):
            qv = qc[near_parabolic]
            w = (
                GAUSSIAN_K_RAD_PER_DAY
                * dt[near_parabolic]
                / np.sqrt(2.0 * np.power(qv, 3.0))
            )
            d = 2.0 * np.sinh(np.arcsinh(1.5 * w) / 3.0)
            x_pf[near_parabolic] = qv * (1.0 - d * d)
            y_pf[near_parabolic] = 2.0 * qv * d

        positions[conic] = _rotate_perifocal(
            x_pf, y_pf, inc[conic], node[conic], argp[conic]
        )

    finite = np.isfinite(positions).all(axis=1)
    return positions[finite], finite
