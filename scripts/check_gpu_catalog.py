#!/usr/bin/env python3
"""Benchmark and validate the arrays prepared for the v2 GPU renderer."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omniverse_solar_system.engine import SolarSystemEngine  # noqa: E402
from omniverse_solar_system.gpu_catalog import evaluate_packed_cpu  # noqa: E402
from omniverse_solar_system.time_utils import datetime_to_jd  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500_000)
    args = parser.parse_args()

    engine = SolarSystemEngine(ROOT)
    try:
        started = perf_counter()
        packed = engine.pack_gpu_asteroids(args.count)
        pack_seconds = perf_counter() - started
        jd = datetime_to_jd(datetime.now(timezone.utc))
        sample_count = min(10_000, packed.count)
        sample = type(packed)(
            source_indices=packed.source_indices[:sample_count],
            semi_major_axis=packed.semi_major_axis[:sample_count],
            eccentricity=packed.eccentricity[:sample_count],
            mean_anomaly_epoch=packed.mean_anomaly_epoch[:sample_count],
            mean_motion=packed.mean_motion[:sample_count],
            epoch_jd=packed.epoch_jd[:sample_count],
            basis_p_j2000=packed.basis_p_j2000[:sample_count],
            basis_q_j2000=packed.basis_q_j2000[:sample_count],
            max_apoapsis_au=packed.max_apoapsis_au,
        )
        started = perf_counter()
        positions = evaluate_packed_cpu(sample, jd)
        reference_seconds = perf_counter() - started
        print(f"Packed records: {packed.count:,}")
        print(f"Resident element data: {packed.bytes / (1024**2):.1f} MiB")
        print(f"Max apoapsis: {packed.max_apoapsis_au:.2f} AU")
        print(f"Pack time: {pack_seconds:.3f} s")
        print(
            f"Reference propagation: {sample_count:,} objects in "
            f"{reference_seconds:.4f} s"
        )
        print(f"Finite sample positions: {np.isfinite(positions).all(axis=1).sum():,}")
    finally:
        engine.close()


if __name__ == "__main__":
    main()
