"""Stream MPC JSON into compact, memory-mappable NumPy arrays."""

from __future__ import annotations

from array import array
from collections.abc import Iterator, Mapping
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .constants import DEG_TO_RAD


FIELDS = ("a", "e", "inc", "node", "argp", "m0", "n", "epoch", "tp", "q", "h")


def iter_json_records(path: Path) -> Iterator[Mapping[str, Any]]:
    """Yield objects from a large top-level JSON array without loading it all.

    ``ijson`` is preferred. A standard-library incremental decoder is retained as
    a fallback so diagnostics and cache construction still work in a minimal venv.
    """
    try:
        import ijson
    except ImportError:
        yield from _iter_json_records_stdlib(path)
        return

    with Path(path).open("rb") as stream:
        for record in ijson.items(stream, "item"):
            if isinstance(record, Mapping):
                yield record


def _iter_json_records_stdlib(path: Path) -> Iterator[Mapping[str, Any]]:
    decoder = json.JSONDecoder()
    buffer = ""
    started = False
    with Path(path).open("r", encoding="utf-8") as stream:
        while True:
            chunk = stream.read(1 << 20)
            if chunk:
                buffer += chunk

            while True:
                buffer = buffer.lstrip()
                if not started:
                    if not buffer:
                        break
                    if buffer[0] != "[":
                        raise ValueError(f"Expected a top-level JSON array in {path}")
                    buffer = buffer[1:]
                    started = True
                    continue

                buffer = buffer.lstrip()
                if buffer.startswith(","):
                    buffer = buffer[1:]
                    continue
                if buffer.startswith("]"):
                    return
                if not buffer:
                    break

                try:
                    record, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    break
                buffer = buffer[end:]
                if isinstance(record, Mapping):
                    yield record

            if not chunk:
                if buffer.strip() not in ("", "]"):
                    raise ValueError(f"Incomplete JSON data in {path}")
                return


def _float(record: Mapping[str, Any], *keys: str) -> float:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return math.nan


def _append_common(buffers: dict[str, array], values: Mapping[str, float]) -> None:
    for key in FIELDS:
        buffers[key].append(float(values.get(key, math.nan)))


def _save_cache(
    output_dir: Path,
    buffers: dict[str, array],
    source: Path,
    skipped: int,
    kind: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    count = len(buffers["e"])
    for name, values in buffers.items():
        dtype = np.float32 if name == "h" else np.float64
        arr = np.frombuffer(values, dtype=np.float64).astype(dtype, copy=True)
        np.save(output_dir / f"{name}.npy", arr, allow_pickle=False)
    manifest = {
        "kind": kind,
        "count": count,
        "skipped": skipped,
        "source": str(source.resolve()),
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "angles": "radians",
        "distances": "AU",
        "epochs": "Julian Date",
        "frame": "heliocentric ecliptic J2000",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def build_asteroid_cache(source: Path, output_dir: Path) -> dict[str, Any]:
    buffers = {name: array("d") for name in FIELDS}
    skipped = 0
    for record in iter_json_records(source):
        e = _float(record, "e")
        a = _float(record, "a")
        epoch = _float(record, "Epoch", "epoch")
        m0 = _float(record, "M", "m") * DEG_TO_RAD
        n = _float(record, "n") * DEG_TO_RAD
        inc = _float(record, "i") * DEG_TO_RAD
        node = _float(record, "Node", "node") * DEG_TO_RAD
        argp = _float(record, "Peri", "peri") * DEG_TO_RAD
        tp = _float(record, "Tp", "tp")
        q = _float(record, "Perihelion_dist", "perihelion_dist")
        h = _float(record, "H", "h")
        usable_ellipse = all(
            math.isfinite(v) for v in (a, e, epoch, m0, inc, node, argp)
        ) and a > 0.0 and 0.0 <= e < 1.0
        usable_conic = all(
            math.isfinite(v) for v in (e, tp, q, inc, node, argp)
        ) and q > 0.0 and e >= 0.0
        if not (usable_ellipse or usable_conic):
            skipped += 1
            continue
        _append_common(
            buffers,
            {
                "a": a,
                "e": e,
                "inc": inc,
                "node": node,
                "argp": argp,
                "m0": m0,
                "n": n,
                "epoch": epoch,
                "tp": tp,
                "q": q,
                "h": h,
            },
        )
    return _save_cache(output_dir, buffers, source, skipped, "asteroids")
