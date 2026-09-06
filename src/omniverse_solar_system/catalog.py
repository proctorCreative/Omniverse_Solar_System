"""Memory-mapped numeric catalog loading."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

import numpy as np


ARRAY_NAMES = (
    "a",
    "e",
    "inc",
    "node",
    "argp",
    "m0",
    "n",
    "epoch",
    "tp",
    "q",
    "h",
)


@dataclass(frozen=True)
class OrbitalCatalog:
    name: str
    arrays: Mapping[str, np.ndarray]
    manifest: Mapping[str, object]

    @property
    def count(self) -> int:
        return int(self.manifest.get("count", len(self.arrays["e"])))

    def __getitem__(self, key: str) -> np.ndarray:
        return self.arrays[key]


def load_catalog(cache_root: Path, name: str, mmap_mode: str | None = "r") -> OrbitalCatalog:
    folder = Path(cache_root) / name
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Missing cache manifest: {manifest_path}. Run scripts/build_cache.py first."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    arrays: dict[str, np.ndarray] = {}
    for array_name in ARRAY_NAMES:
        path = folder / f"{array_name}.npy"
        if not path.exists():
            raise FileNotFoundError(f"Missing cache array: {path}")
        arrays[array_name] = np.load(path, mmap_mode=mmap_mode)
    return OrbitalCatalog(name=name, arrays=arrays, manifest=manifest)
