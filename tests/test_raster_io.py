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


def test_read_geotiff_reads_an_lzw_compressed_file(tmp_path: Path) -> None:
    """The compression production actually uses — decoded by imagecodecs.

    Every GHS-POP and GHS-BUILT-S GeoTIFF JRC publishes is LZW-compressed
    (``docs/sources/ghspop.md``, ``docs/sources/ghsbuilts.md``). Until this
    test was added on 2026-08-13 (#443), **nothing in this suite ever wrote
    a compressed TIFF** — every ``imwrite`` above and in the viewpoint
    tests is uncompressed. So the decode path that handles 100% of
    production rasters had never been exercised on any interpreter.

    Why that is worse than an ordinary coverage gap: ``imagecodecs`` is
    imported by **nothing** in ``src/``. It is reached implicitly, inside
    ``read_geotiff``, when ``page.asarray()`` hits COMPRESSION 5 and
    tifffile dispatches to ``imagecodecs.lzw_decode``. There is no
    pure-Python fallback for LZW. An import-graph audit therefore concludes
    the dependency is unused and removable — and removing it would break
    every production raster read while leaving the whole suite green. That
    is the exact shape of the audit that got the views-frames floor wrong
    (C-337): every step true, conclusion wrong, because the question was
    about imports rather than about what actually runs.

    Kept as a separate function rather than parametrising the test above:
    WET before DRY, and the two tests answer different questions.
    """
    data = np.arange(16, dtype=np.float32).reshape(4, 4)
    tif_path = tmp_path / "lzw.tif"

    tie_x, tie_y = -180.0, 90.0
    sc_x, sc_y = 0.00833333, 0.00833333

    tifffile.imwrite(
        str(tif_path),
        data,
        compression="lzw",
        metadata=None,
        extratags=[
            (33922, 12, 6, (0.0, 0.0, 0.0, tie_x, tie_y, 0.0)),
            (33550, 12, 3, (sc_x, sc_y, 0.0)),
        ],
    )

    arr, rx, ry, rsx, rsy = read_geotiff(tif_path)

    np.testing.assert_array_equal(arr, data)
    assert arr.dtype == np.float32
    assert rx == pytest.approx(tie_x)
    assert ry == pytest.approx(tie_y)
    assert rsx == pytest.approx(sc_x)
    assert rsy == pytest.approx(sc_y)
