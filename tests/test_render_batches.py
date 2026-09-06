import numpy as np
import pytest

from omniverse_solar_system.render_batches import (
    iter_owned_position_batches,
    owned_float32_positions,
)


def test_owned_positions_are_float32_contiguous_and_independent():
    source = np.arange(60, dtype=np.float64).reshape(20, 3)
    view = source[5:10]
    result = owned_float32_positions(view)
    assert result.dtype == np.float32
    assert result.flags.c_contiguous
    assert result.flags.owndata
    source[5, 0] = -999
    assert result[0, 0] != -999


def test_owned_batches_have_expected_bounds_and_ownership():
    source = np.arange(33, dtype=np.float64).reshape(11, 3)
    batches = list(iter_owned_position_batches(source, 4))
    assert [(start, stop) for start, stop, _ in batches] == [(0, 4), (4, 8), (8, 11)]
    assert all(batch.flags.owndata for _, _, batch in batches)
    assert [len(batch) for _, _, batch in batches] == [4, 4, 3]


def test_owned_positions_reject_bad_shape():
    with pytest.raises(ValueError):
        owned_float32_positions(np.zeros((3, 2)))
