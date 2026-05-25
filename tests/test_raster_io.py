"""Direct tests for datafactory_viewpoint.raster_io."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import tifffile

from datafactory_viewpoint.raster_io import read_geotiff


def test_read_geotiff_returns_tuple(tmp_path: Path) -> None:
    """read_geotiff returns (array, tie_x, tie_y, scale_x, scale_y)."""
    data = np.arange(16, dtype=np.float32).reshape(4, 4)
    tif_path = tmp_path / "test.tif"

    tie_x, tie_y = -180.0, 90.0
    sc_x, sc_y = 0.00833333, 0.00833333

    tifffile.imwrite(
        str(tif_path),
        data,
        metadata=None,
        extratags=[
            (33922, 12, 6, (0.0, 0.0, 0.0, tie_x, tie_y, 0.0)),
            (33550, 12, 3, (sc_x, sc_y, 0.0)),
        ],
    )

    arr, rx, ry, rsx, rsy = read_geotiff(tif_path)

    assert arr.shape == (4, 4)
    assert arr.dtype == np.float32
    np.testing.assert_array_equal(arr, data)
    assert rx == pytest.approx(tie_x)
    assert ry == pytest.approx(tie_y)
    assert rsx == pytest.approx(sc_x)
    assert rsy == pytest.approx(sc_y)
