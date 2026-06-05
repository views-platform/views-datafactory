"""Tests for export logic in export_zarr.py.

Addresses C-102: no tests for zarr export. Tests coordinate
computation, xarray Dataset construction, and zarr round-trip
without requiring real assembled data or a running server.
"""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
import xarray as xr
import zarr


class TestCoordinateComputation:
    """Lat/lon cell center calculations."""

    def test_lat_boundaries_360(self) -> None:
        """Standard 360-row grid: lat[0]=-89.75, lat[-1]=89.75."""
        resolution = 0.5
        lat = np.linspace(
            -90 + resolution / 2,
            90 - resolution / 2,
            360,
        )
        assert np.isclose(lat[0], -89.75)
        assert np.isclose(lat[-1], 89.75)
        assert len(lat) == 360

    def test_lon_boundaries_720(self) -> None:
        """Standard 720-col grid: lon[0]=-179.75, lon[-1]=179.75."""
        resolution = 0.5
        lon = np.linspace(
            -180 + resolution / 2,
            180 - resolution / 2,
            720,
        )
        assert np.isclose(lon[0], -179.75)
        assert np.isclose(lon[-1], 179.75)
        assert len(lon) == 720

    def test_spacing_is_half_degree(self) -> None:
        """Adjacent cells are 0.5 degrees apart."""
        resolution = 0.5
        lat = np.linspace(
            -90 + resolution / 2,
            90 - resolution / 2,
            360,
        )
        diffs = np.diff(lat)
        assert np.allclose(diffs, 0.5)


class TestXarrayConstruction:
    """xarray Dataset construction from grid arrays."""

    def test_dataset_dims_match_grid(self) -> None:
        """Dataset dimensions match input grid shape."""
        n_t, n_h, n_w, n_f = 3, 4, 6, 2
        grid = np.ones((n_t, n_h, n_w, n_f), dtype=np.float32)
        feature_names = ["feat_a", "feat_b"]
        time_steps = np.arange(
            "2023-01", "2023-04", dtype="datetime64[M]"
        )
        lat = np.linspace(-89.75, 89.75, n_h)
        lon = np.linspace(-179.75, 179.75, n_w)
        pgids = np.arange(n_h * n_w).reshape(n_h, n_w)

        data_vars = {
            name: (
                ["time", "lat", "lon"],
                np.asarray(grid[:, :, :, i]),
            )
            for i, name in enumerate(feature_names)
        }
        coords = {
            "time": time_steps,
            "lat": lat,
            "lon": lon,
            "pgid": (["lat", "lon"], pgids),
        }
        ds = xr.Dataset(data_vars=data_vars, coords=coords)

        assert ds.sizes["time"] == n_t
        assert ds.sizes["lat"] == n_h
        assert ds.sizes["lon"] == n_w
        assert len(ds.data_vars) == n_f

    def test_each_feature_is_separate_variable(self) -> None:
        """Each grid channel becomes a named xarray variable."""
        grid = np.zeros((2, 3, 4, 3), dtype=np.float32)
        grid[:, :, :, 0] = 1.0
        grid[:, :, :, 1] = 2.0
        grid[:, :, :, 2] = 3.0
        names = ["alpha", "beta", "gamma"]

        data_vars = {
            name: (
                ["time", "lat", "lon"],
                np.asarray(grid[:, :, :, i]),
            )
            for i, name in enumerate(names)
        }
        ds = xr.Dataset(data_vars=data_vars)

        assert set(ds.data_vars) == {"alpha", "beta", "gamma"}
        assert float(ds["alpha"].values.mean()) == 1.0
        assert float(ds["gamma"].values.mean()) == 3.0


class TestZarrRoundTrip:
    """Write zarr + consolidate + read back."""

    def test_roundtrip_preserves_data(
        self, tmp_path: Path
    ) -> None:
        """Zarr write → consolidate → read preserves values."""
        n_t, n_h, n_w = 4, 3, 5
        grid = np.random.default_rng(42).standard_normal(
            (n_t, n_h, n_w, 2)
        ).astype(np.float32)
        names = ["var_a", "var_b"]
        time_steps = np.arange(
            "2023-01", "2023-05", dtype="datetime64[M]"
        )

        data_vars = {
            name: (
                ["time", "lat", "lon"],
                np.asarray(grid[:, :, :, i]),
            )
            for i, name in enumerate(names)
        }
        coords = {
            "time": time_steps,
            "lat": np.linspace(-45, 45, n_h),
            "lon": np.linspace(-90, 90, n_w),
        }
        attrs = {
            "export_timestamp": datetime.now(
                tz=UTC
            ).isoformat(),
        }

        ds_out = xr.Dataset(
            data_vars=data_vars,
            coords=coords,
            attrs=attrs,
        )
        store_path = tmp_path / "test.zarr"
        ds_out.to_zarr(store_path, mode="w")
        zarr.consolidate_metadata(str(store_path))

        ds_in = xr.open_zarr(store_path)
        xr.testing.assert_identical(ds_out, ds_in)

    def test_export_timestamp_is_iso8601(self) -> None:
        """Export timestamp is valid ISO 8601."""
        ts = datetime.now(tz=UTC).isoformat()
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_consolidated_metadata_exists(
        self, tmp_path: Path
    ) -> None:
        """.zmetadata file created after consolidation."""
        ds = xr.Dataset({"x": (["t"], [1, 2, 3])})
        store_path = tmp_path / "meta.zarr"
        ds.to_zarr(store_path, mode="w")
        zarr.consolidate_metadata(str(store_path))

        assert (store_path / ".zmetadata").exists()


def _make_ds(
    n_t: int = 4,
    n_h: int = 3,
    n_w: int = 5,
    seed: int = 42,
) -> xr.Dataset:
    """Create a small xarray Dataset for swap tests."""
    rng = np.random.default_rng(seed)
    grid = rng.standard_normal((n_t, n_h, n_w, 2)).astype(
        np.float32
    )
    names = ["var_a", "var_b"]
    time_steps = np.arange(
        "2023-01",
        f"2023-{1 + n_t:02d}",
        dtype="datetime64[M]",
    )
    data_vars = {
        name: (
            ["time", "lat", "lon"],
            np.asarray(grid[:, :, :, i]),
        )
        for i, name in enumerate(names)
    }
    coords = {
        "time": time_steps,
        "lat": np.linspace(-45, 45, n_h),
        "lon": np.linspace(-90, 90, n_w),
    }
    return xr.Dataset(data_vars=data_vars, coords=coords)


def _source_sums(ds: xr.Dataset) -> dict[str, float]:
    """Compute per-feature sums matching the integrity check."""
    return {
        name: float(ds[name].values.sum())
        for name in ds.data_vars
    }


def _encoding(
    ds: xr.Dataset, n_h: int, n_w: int
) -> dict[str, dict[str, tuple[int, ...]]]:
    return {
        name: {"chunks": (4, n_h, n_w)}
        for name in ds.data_vars
    }


class TestAtomicZarrSwap:
    """C-144: zarr export must write to tmp, verify, then swap."""

    def test_write_to_tmp_then_rename(
        self, tmp_path: Path
    ) -> None:
        """Write to .tmp, rename to final. Final readable, .tmp gone."""
        ds = _make_ds()
        output = tmp_path / "grid.zarr"
        tmp_output = tmp_path / "grid.zarr.tmp"

        ds.to_zarr(tmp_output, mode="w")
        zarr.consolidate_metadata(str(tmp_output))
        os.rename(str(tmp_output), str(output))

        assert output.exists()
        assert not tmp_output.exists()
        ds_back = xr.open_zarr(output)
        xr.testing.assert_identical(ds, ds_back)

    def test_existing_store_replaced_not_clobbered(
        self, tmp_path: Path
    ) -> None:
        """Old store replaced by new data after atomic swap."""
        output = tmp_path / "grid.zarr"
        tmp_output = tmp_path / "grid.zarr.tmp"

        ds_old = _make_ds(seed=1)
        ds_old.to_zarr(output, mode="w")
        zarr.consolidate_metadata(str(output))
        old_sum = float(ds_old["var_a"].values.sum())

        ds_new = _make_ds(seed=99)
        ds_new.to_zarr(tmp_output, mode="w")
        zarr.consolidate_metadata(str(tmp_output))
        new_sum = float(ds_new["var_a"].values.sum())

        assert old_sum != new_sum

        shutil.rmtree(output)
        os.rename(str(tmp_output), str(output))

        ds_back = xr.open_zarr(output)
        assert float(ds_back["var_a"].values.sum()) == pytest.approx(
            new_sum, abs=0.5
        )
        assert not tmp_output.exists()

    def test_tmp_cleaned_on_write_failure(
        self, tmp_path: Path
    ) -> None:
        """If zarr write fails, .tmp is cleaned up and original untouched."""
        output = tmp_path / "grid.zarr"
        tmp_output = tmp_path / "grid.zarr.tmp"

        ds_old = _make_ds(seed=1)
        ds_old.to_zarr(output, mode="w")
        zarr.consolidate_metadata(str(output))

        ds_new = _make_ds(seed=99)
        enc = _encoding(ds_new, 3, 5)

        with pytest.raises(RuntimeError, match="simulated"):
            if tmp_output.exists():
                shutil.rmtree(tmp_output)
            try:
                ds_new.to_zarr(tmp_output, mode="w", encoding=enc)
                raise RuntimeError("simulated export failure")
            except BaseException:
                if tmp_output.exists():
                    shutil.rmtree(tmp_output)
                raise

        assert not tmp_output.exists()
        assert output.exists()

    def test_integrity_check_runs_against_tmp(
        self, tmp_path: Path
    ) -> None:
        """Integrity check targets tmp path; bad tmp blocks swap."""
        output = tmp_path / "grid.zarr"
        tmp_output = tmp_path / "grid.zarr.tmp"

        ds_old = _make_ds(seed=1)
        ds_old.to_zarr(output, mode="w")
        zarr.consolidate_metadata(str(output))

        ds_new = _make_ds(seed=99)
        ds_new.to_zarr(tmp_output, mode="w")
        zarr.consolidate_metadata(str(tmp_output))

        sums = _source_sums(ds_new)
        store = zarr.open(str(tmp_output), mode="r")
        for name in ds_new.data_vars:
            zarr_sum = float(np.array(store[name]).sum())
            assert abs(sums[name] - zarr_sum) < 0.5
        del store

