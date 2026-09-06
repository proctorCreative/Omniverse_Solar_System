#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omniverse_solar_system.paths import resolve_raw_data_root
from omniverse_solar_system.spice_ephemeris import SpiceEphemeris


def main() -> None:
    parser = argparse.ArgumentParser(description="Check SPICE planet positions")
    parser.add_argument(
        "--raw-data",
        type=Path,
        help="RawData directory (or project directory containing RawData)",
    )
    args = parser.parse_args()
    raw = resolve_raw_data_root(ROOT, args.raw_data)
    print(f"Using RawData: {raw}")

    ephemeris = SpiceEphemeris(
        raw / "spice" / "de440.bsp",
        raw / "spice" / "naif0012.tls",
    )
    try:
        names, positions = ephemeris.planet_positions(datetime.now(timezone.utc))
        for name, xyz in zip(names, positions):
            print(f"{name:8s} {xyz[0]: .9f} {xyz[1]: .9f} {xyz[2]: .9f} AU")
    finally:
        ephemeris.close()


if __name__ == "__main__":
    main()
