"""Pure NumPy helpers for renderer-safe point batches."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np


def owned_float32_positions(positions: np.ndarray) -> np.ndarray:
    """Return an owned, C-contiguous ``(N, 3)`` float32 array.

    A plain NumPy slice is usually a view into the complete catalog allocation.
    Some native bindings inspect or retain that base allocation, which defeats
    batching. An explicit copy guarantees that each renderer upload owns only
    the memory for its batch.
    """
    array = np.asarray(positions)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError(f"Expected positions shaped (N, 3), got {array.shape}")
    return np.array(array, dtype=np.float32, order="C", copy=True)


def iter_owned_position_batches(
    positions: np.ndarray,
    batch_size: int,
) -> Iterator[tuple[int, int, np.ndarray]]:
    """Yield ``(start, stop, owned_batch)`` tuples."""
    batch_size = int(batch_size)
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    count = len(positions)
    for start in range(0, count, batch_size):
        stop = min(start + batch_size, count)
        yield start, stop, owned_float32_positions(positions[start:stop])
