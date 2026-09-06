#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omniverse_solar_system.engine import SolarSystemEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute one full solar-system snapshot")
    parser.add_argument(
        "--raw-data",
        type=Path,
        help="RawData directory (or project directory containing RawData)",
    )
    parser.add_argument("--cache", type=Path, help="Cache directory")
    args = parser.parse_args()

    start = time.perf_counter()
    engine = SolarSystemEngine(ROOT, raw_data_root=args.raw_data, cache_root=args.cache)
    try:
        print(f"Using RawData: {engine.raw_data_root}")
        print(f"Using Cache:   {engine.cache_root}")
        snapshot = engine.compute_snapshot(datetime.now(timezone.utc))
    finally:
        engine.close()
    elapsed = time.perf_counter() - start
    print(f"UTC: {snapshot.when_utc.isoformat()}")
    print(f"JD: {snapshot.jd_utc:.8f}")
    print(f"Planets: {len(snapshot.planet_positions):,}")
    print(f"Asteroids: {len(snapshot.asteroid_positions):,}")
    print(f"Elapsed: {elapsed:.3f} s")
    print("Primary planet positions (AU, J2000):")
    for name, xyz in zip(snapshot.planet_names, snapshot.planet_positions):
        print(f"  {name:8s} {xyz}")


if __name__ == "__main__":
    main()
