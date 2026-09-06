#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omniverse_solar_system.cache_builder import iter_json_records
from omniverse_solar_system.paths import resolve_raw_data_root


def inspect_json(path: Path) -> None:
    print(f"\n{path}")
    print(f"  size: {path.stat().st_size:,} bytes")
    iterator = iter_json_records(path)
    try:
        first = next(iterator)
    except StopIteration:
        print("  EMPTY")
        return
    print(f"  first-record keys ({len(first)}):")
    print("   ", ", ".join(sorted(first.keys())))
    print("  selected values:")
    selected = {
        key: first.get(key)
        for key in (
            "Number", "Name", "Principal_desig", "Designation_and_name",
            "Epoch", "M", "a", "e", "i", "Node", "Peri",
        )
        if key in first
    }
    print(json.dumps(selected, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect MPC asteroid and SPICE inputs")
    parser.add_argument(
        "--raw-data",
        type=Path,
        help="RawData directory (or project directory containing RawData)",
    )
    args = parser.parse_args()

    raw = resolve_raw_data_root(ROOT, args.raw_data)
    print(f"Using RawData: {raw}")
    expected = (
        raw / "mpc" / "mpcorb_extended.json",
        raw / "spice" / "de440.bsp",
        raw / "spice" / "naif0012.tls",
    )
    missing = [path for path in expected if not path.exists()]
    if missing:
        print("Missing expected files:")
        for path in missing:
            print(f"  {path}")
        raise SystemExit(1)
    inspect_json(expected[0])
    for path in expected[1:]:
        print(f"\n{path}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
