"""Project, raw-data, cache, and shared background path resolution.

The code may be installed directly in the user's project directory or extracted
into a versioned sibling directory. RawData and the large star-map EXR are
intentionally never copied into release archives, so discovery must not assume
they live beside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable

RAW_DATA_ENV = "OMNIVERSE_SOLAR_SYSTEM_RAW_DATA"
CACHE_ENV = "OMNIVERSE_SOLAR_SYSTEM_CACHE"
STARMAP_ENV = "OMNIVERSE_SOLAR_SYSTEM_STARMAP"
STARMAP_FILENAME = "starmap_2020_16k.exr"


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    raw_data_root: Path
    cache_root: Path


def _looks_like_raw_data(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "mpc").is_dir()
        and (path / "spice").is_dir()
    )


def _deduplicate(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        normalized = path.expanduser().resolve(strict=False)
        key = str(normalized)
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def raw_data_candidates(project_root: Path, explicit: Path | None = None) -> list[Path]:
    """Return plausible RawData directories in priority order."""

    root = Path(project_root).expanduser().resolve(strict=False)
    candidates: list[Path] = []

    if explicit is not None:
        explicit_path = Path(explicit).expanduser()
        candidates.append(
            explicit_path / "RawData"
            if explicit_path.name != "RawData" and (explicit_path / "RawData").exists()
            else explicit_path
        )

    env_value = os.environ.get(RAW_DATA_ENV)
    if env_value:
        env_path = Path(env_value).expanduser()
        candidates.append(
            env_path / "RawData"
            if env_path.name != "RawData" and (env_path / "RawData").exists()
            else env_path
        )

    # Normal installation. ``solar-system-data`` is the preferred canonical
    # sibling repository; a local RawData link remains supported.
    candidates.append(root / "RawData")
    candidates.append(root / "solar-system-data")

    # Common extraction layouts, including:
    #   .../Omniverse_Solar_System_v0.1/Omniverse_Solar_System
    # while data remains at:
    #   .../Omniverse_Solar_System/RawData
    lineage = [root, *root.parents]
    for ancestor in lineage[:6]:
        candidates.append(ancestor / "RawData")
        candidates.append(ancestor / "solar-system-data")
        candidates.append(ancestor / "Omniverse_Solar_System" / "RawData")

    return _deduplicate(candidates)


def resolve_raw_data_root(project_root: Path, explicit: Path | None = None) -> Path:
    candidates = raw_data_candidates(project_root, explicit)
    for candidate in candidates:
        if _looks_like_raw_data(candidate):
            return candidate

    checked = "\n".join(f"  - {path}" for path in candidates)
    raise FileNotFoundError(
        "Could not locate RawData. Checked:\n"
        f"{checked}\n"
        f"Set {RAW_DATA_ENV}=/absolute/path/to/RawData or pass --raw-data."
    )


def resolve_cache_root(project_root: Path, explicit: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve(strict=False)
    env_value = os.environ.get(CACHE_ENV)
    if env_value:
        return Path(env_value).expanduser().resolve(strict=False)
    return Path(project_root).expanduser().resolve(strict=False) / "Cache"


def starmap_candidates(
    project_root: Path,
    *,
    raw_data_root: Path | None = None,
    explicit: Path | None = None,
) -> list[Path]:
    """Return plausible star-map EXR paths in priority order.

    The canonical installation is the shared 16K EXR under
    ``solar-system-data/backgrounds``. An environment override is provided for
    other machines without requiring code changes.
    """

    root = Path(project_root).expanduser().resolve(strict=False)
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit).expanduser())

    env_value = os.environ.get(STARMAP_ENV)
    if env_value:
        candidates.append(Path(env_value).expanduser())

    if raw_data_root is not None:
        candidates.append(Path(raw_data_root) / "backgrounds" / STARMAP_FILENAME)

    candidates.extend(
        [
            root / "RawData" / "backgrounds" / STARMAP_FILENAME,
            root / "solar-system-data" / "backgrounds" / STARMAP_FILENAME,
        ]
    )
    for ancestor in [root, *root.parents][:6]:
        candidates.append(
            ancestor / "solar-system-data" / "backgrounds" / STARMAP_FILENAME
        )
    return _deduplicate(candidates)


def resolve_starmap_path(
    project_root: Path,
    *,
    raw_data_root: Path | None = None,
    explicit: Path | None = None,
    require_exists: bool = False,
) -> Path:
    """Resolve the shared star-map path.

    When ``require_exists`` is false, return the highest-priority path even when
    it is not present so the UI can report the exact expected location.
    """

    candidates = starmap_candidates(
        project_root,
        raw_data_root=raw_data_root,
        explicit=explicit,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    if not require_exists:
        return candidates[0]

    checked = "\n".join(f"  - {path}" for path in candidates)
    raise FileNotFoundError(
        "Could not locate the star-map EXR. Checked:\n"
        f"{checked}\n"
        f"Set {STARMAP_ENV}=/absolute/path/to/{STARMAP_FILENAME}."
    )


def resolve_project_paths(
    project_root: Path,
    *,
    raw_data_root: Path | None = None,
    cache_root: Path | None = None,
) -> ProjectPaths:
    root = Path(project_root).expanduser().resolve(strict=False)
    return ProjectPaths(
        project_root=root,
        raw_data_root=resolve_raw_data_root(root, raw_data_root),
        cache_root=resolve_cache_root(root, cache_root),
    )
