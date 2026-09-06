#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omniverse_solar_system.cache_builder import build_asteroid_cache
from omniverse_solar_system.paths import resolve_cache_root, resolve_raw_data_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the memory-mapped MPC asteroid cache")
    parser.add_argument("--force", action="store_true", help="Delete existing asteroid cache first")
    parser.add_argument(
        "--raw-data",
        type=Path,
        help="RawData directory (or project directory containing RawData)",
    )
    parser.add_argument("--cache", type=Path, help="Cache output directory")
    args = parser.parse_args()

    raw = resolve_raw_data_root(ROOT, args.raw_data)
    cache = resolve_cache_root(ROOT, args.cache)
    asteroid_source = raw / "mpc" / "mpcorb_extended.json"
    if not asteroid_source.is_file():
        raise FileNotFoundError(f"Missing input file: {asteroid_source}")

    asteroid_cache = cache / "asteroids"
    if args.force and asteroid_cache.exists():
        shutil.rmtree(asteroid_cache)
    cache.mkdir(parents=True, exist_ok=True)

    print(f"Using RawData: {raw}")
    print(f"Using Cache:   {cache}")
    print(f"Building asteroid cache from {asteroid_source}")
    asteroids = build_asteroid_cache(asteroid_source, asteroid_cache)
    print(json.dumps(asteroids, indent=2))


if __name__ == "__main__":
    main()
