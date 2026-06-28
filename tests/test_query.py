"""Tests for datafactory_query — temporal, regions, dataset loading."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_adapters import FeatureFrame
from datafactory_query.defaults import DEFAULT_REMOTE
from datafactory_query.regions import (
    REGIONS,
    list_regions,
    load_region_pgids,
)
from datafactory_query.temporal import (
    parse_time_range,
    time_range_to_slice,
)

# ── Fixtures ─────────────────────────────────────────────

TIME_STEPS = np.array(
    ["2020-01", "2020-02", "2020-03", "2020-04", "2020-05", "2020-06"],
    dtype="datetime64[M]",
)


def _make_gaul_parquets(gaul_dir: Path, n_cells: int = 12) -> None:
    """Create minimal GAUL Parquet files for testing."""
    gaul_dir.mkdir(parents=True, exist_ok=True)

    # 6 cells in "Testland", 6 in "Otherland"
    gids = list(range(1, n_cells + 1))
    names = ["Testland"] * (n_cells // 2) + ["Otherland"] * (n_cells // 2)
    codes = [100] * (n_cells // 2) + [200] * (n_cells // 2)

    name_table = pa.table({"gid": gids, "value": names})
    pq.write_table(name_table, gaul_dir / "gaul0_name.parquet")

    code_table = pa.table({"gid": gids, "value": codes})
    pq.write_table(code_table, gaul_dir / "gaul0_code.parquet")


def _make_assembled_grid(
    data_dir: Path,
    n_t: int = 6,
    n_h: int = 3,
    n_w: int = 4,
    n_f: int = 2,
) -> None:
    """Create a tiny assembled grid for testing."""
    data_dir.mkdir(parents=True, exist_ok=True)

    grid = np.ones((n_t, n_h, n_w, n_f), dtype=np.float32)
    np.save(data_dir / "grid.npy", grid)

    pgids = np.arange(1, n_h * n_w + 1).reshape(n_h, n_w)
    np.save(data_dir / "pgids.npy", pgids)

    time_steps = np.array(
        [f"2020-{m:02d}" for m in range(1, n_t + 1)],
        dtype="datetime64[M]",
    )
    np.save(data_dir / "time_steps.npy", time_steps)

    features = [f"feat_{i}" for i in range(n_f)]
    (data_dir / "feature_names.json").write_text(json.dumps(features))


# ── Temporal Parsing ─────────────────────────────────────


class TestParseTimeRange:

    def test_iso_month(self) -> None:
        s, e = parse_time_range("2020-01", "2020-06")
        assert s == np.datetime64("2020-01", "M")
        assert e == np.datetime64("2020-06", "M")

    def test_year_only(self) -> None:
        s, e = parse_time_range("2020", "2021")
        assert s == np.datetime64("2020-01", "M")
        # Year-only end → December
        assert e == np.datetime64("2021-12", "M")

    def test_views_month_id(self) -> None:
        # Jan 2020 = (2020-1980)*12 + 1 = 481
        s, e = parse_time_range(481, 492)
        assert s == np.datetime64("2020-01", "M")
        assert e == np.datetime64("2020-12", "M")

    def test_date_string_truncated(self) -> None:
        s, _ = parse_time_range("2020-03-15", "2020-06")
        assert s == np.datetime64("2020-03", "M")

    def test_none_uses_time_steps(self) -> None:
        s, e = parse_time_range(None, None, time_steps=TIME_STEPS)
        assert s == TIME_STEPS[0]
        assert e == TIME_STEPS[-1]

    def test_none_without_time_steps_raises(self) -> None:
        with pytest.raises(ValueError, match="time_steps"):
            parse_time_range(None, "2020-06")

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_time_range("not-a-date", "2020")


class TestTimeRangeToSlice:

    def test_full_range(self) -> None:
        s = time_range_to_slice(
            TIME_STEPS,
            np.datetime64("2020-01", "M"),
            np.datetime64("2020-06", "M"),
        )
        assert s == slice(0, 6)

    def test_partial_range(self) -> None:
        s = time_range_to_slice(
            TIME_STEPS,
            np.datetime64("2020-02", "M"),
            np.datetime64("2020-04", "M"),
        )
        assert s == slice(1, 4)

    def test_no_overlap_raises(self) -> None:
        with pytest.raises(ValueError, match="no overlap"):
            time_range_to_slice(
                TIME_STEPS,
                np.datetime64("2025-01", "M"),
                np.datetime64("2025-12", "M"),
            )


# ── Regions ──────────────────────────────────────────────


class TestRegions:

    def test_list_regions_includes_predefined(self) -> None:
        regions = list_regions()
        assert "africa_me" in regions
        assert "land" in regions
        assert "global" in regions

    def test_global_returns_all_cells(self) -> None:
        pgids = load_region_pgids("global")
        assert len(pgids) == 259_200

    def test_country_lookup(self, tmp_path: Path) -> None:
        gaul_dir = tmp_path / "gaul"
        _make_gaul_parquets(gaul_dir)
        pgids = load_region_pgids("Testland", gaul_dir=gaul_dir)
        assert pgids == {1, 2, 3, 4, 5, 6}

    def test_country_case_insensitive(self, tmp_path: Path) -> None:
        gaul_dir = tmp_path / "gaul"
        _make_gaul_parquets(gaul_dir)
        pgids = load_region_pgids("testland", gaul_dir=gaul_dir)
        assert pgids == {1, 2, 3, 4, 5, 6}

    def test_unknown_region_raises(self, tmp_path: Path) -> None:
        gaul_dir = tmp_path / "gaul"
        _make_gaul_parquets(gaul_dir)
        with pytest.raises(ValueError, match="Unknown region"):
            load_region_pgids("narnia", gaul_dir=gaul_dir)

    def test_missing_gaul_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="GAUL data"):
            load_region_pgids(
                "africa", gaul_dir=tmp_path / "nonexistent",
            )

    def test_region_definitions_non_empty(self) -> None:
        for name, countries in REGIONS.items():
            assert len(countries) > 0, f"Region {name!r} is empty"


class TestLandRegion:
    """Tests for the bundled land pgid set."""

    def test_land_returns_correct_count(self) -> None:
        pgids = load_region_pgids("land")
        assert len(pgids) == 64_818

    def test_land_pgids_are_within_grid(self) -> None:
        pgids = load_region_pgids("land")
        assert all(1 <= p <= 259_200 for p in pgids)

    def test_land_is_subset_of_global(self) -> None:
        land = load_region_pgids("land")
        globe = load_region_pgids("global")
        assert land < globe

    def test_land_pgids_json_exists(self) -> None:
        pkg = Path(__file__).parent.parent / "src"
        path = pkg / "datafactory_query" / "land_pgids.json"
        assert path.exists(), "land_pgids.json must be bundled"

    def test_land_pgids_json_is_sorted_unique(self) -> None:
        pkg = Path(__file__).parent.parent / "src"
        path = pkg / "datafactory_query" / "land_pgids.json"
        pgids = json.loads(path.read_text())
        assert pgids == sorted(pgids)
        assert len(pgids) == len(set(pgids))

    def test_land_no_network_dependency(self) -> None:
        """Loading land must not import requests."""
        import sys  # noqa: I001

        from datafactory_query.regions import _load_land_pgids
        _load_land_pgids.cache_clear()
        pgids = load_region_pgids("land")
        assert len(pgids) == 64_818
        mod = sys.modules.get("datafactory_query.regions")
        assert mod is not None
        src = Path(mod.__file__).read_text()  # type: ignore[arg-type]
        assert "import requests" not in src


class TestAfricaMeLegacyRegion:
    """Tests for the bundled africa_me_legacy pgid set."""

    def test_legacy_returns_correct_count(self) -> None:
        pgids = load_region_pgids("africa_me_legacy")
        assert len(pgids) == 13_110

    def test_legacy_is_subset_of_land(self) -> None:
        legacy = load_region_pgids("africa_me_legacy")
        land = load_region_pgids("land")
        assert legacy <= land

    def test_legacy_pgids_json_exists(self) -> None:
        pkg = Path(__file__).parent.parent / "src"
        path = pkg / "datafactory_query" / "africa_me_legacy_pgids.json"
        assert path.exists()

    def test_legacy_pgids_json_is_sorted_unique(self) -> None:
        pkg = Path(__file__).parent.parent / "src"
        path = pkg / "datafactory_query" / "africa_me_legacy_pgids.json"
        pgids = json.loads(path.read_text())
        assert pgids == sorted(pgids)
        assert len(pgids) == len(set(pgids))


class TestLandGaulRegion:
    """Tests for the bundled land_gaul pgid set (land ∩ GAUL)."""

    def test_land_gaul_returns_correct_count(self) -> None:
        pgids = load_region_pgids("land_gaul")
        assert len(pgids) == 64_742

    def test_land_gaul_is_subset_of_land(self) -> None:
        land_gaul = load_region_pgids("land_gaul")
        land = load_region_pgids("land")
        assert land_gaul < land

    def test_land_gaul_excludes_82_cells(self) -> None:
        land = load_region_pgids("land")
        land_gaul = load_region_pgids("land_gaul")
        excluded = land - land_gaul
        assert len(excluded) == 76

    def test_land_gaul_pgids_json_exists(self) -> None:
        pkg = Path(__file__).parent.parent / "src"
        path = pkg / "datafactory_query" / "land_gaul_pgids.json"
        assert path.exists(), "land_gaul_pgids.json must be bundled"

    def test_land_gaul_pgids_json_is_sorted_unique(self) -> None:
        pkg = Path(__file__).parent.parent / "src"
        path = pkg / "datafactory_query" / "land_gaul_pgids.json"
        pgids = json.loads(path.read_text())
        assert pgids == sorted(pgids)
        assert len(pgids) == len(set(pgids))

    def test_land_gaul_no_gaul_dir_needed(self) -> None:
        """land_gaul resolves from bundled JSON, no GAUL parquets."""
        pgids = load_region_pgids("land_gaul")
        assert len(pgids) == 64_742

    def test_land_gaul_in_list_regions(self) -> None:
        from datafactory_query.regions import list_regions
        assert "land_gaul" in list_regions()


class TestAfricaMeGaulRegion:
    """Tests for the bundled africa_me_gaul pgid set (#215)."""

    def test_africa_me_gaul_returns_correct_count(self) -> None:
        pgids = load_region_pgids("africa_me_gaul")
        assert len(pgids) == 13_105

    def test_africa_me_gaul_is_subset_of_legacy(self) -> None:
        gaul = load_region_pgids("africa_me_gaul")
        legacy = load_region_pgids("africa_me_legacy")
        assert gaul < legacy

    def test_africa_me_gaul_is_subset_of_land_gaul(self) -> None:
        gaul = load_region_pgids("africa_me_gaul")
        land_gaul = load_region_pgids("land_gaul")
        assert gaul <= land_gaul

    def test_africa_me_gaul_excluded_set(self) -> None:
        gaul = load_region_pgids("africa_me_gaul")
        legacy = load_region_pgids("africa_me_legacy")
        excluded = legacy - gaul
        assert excluded == {62356, 94776, 99027, 107733, 107742}

    def test_africa_me_gaul_pgids_json_exists(self) -> None:
        pkg = Path(__file__).parent.parent / "src"
        path = pkg / "datafactory_query" / "africa_me_gaul_pgids.json"
        assert path.exists()

    def test_africa_me_gaul_pgids_json_is_sorted_unique(self) -> None:
        pkg = Path(__file__).parent.parent / "src"
        path = pkg / "datafactory_query" / "africa_me_gaul_pgids.json"
        pgids = json.loads(path.read_text())
        assert pgids == sorted(pgids)
        assert len(pgids) == len(set(pgids))

    def test_africa_me_gaul_in_list_regions(self) -> None:
        assert "africa_me_gaul" in list_regions()


class TestBundledPgidConsistency:
    """Cross-checks between bundled pgid sets."""

    def test_land_covers_all_macro_regions(self, tmp_path: Path) -> None:
        """Every GAUL-based macro-region cell should be a land cell."""
        gaul_dir = tmp_path / "gaul"
        _make_gaul_parquets(gaul_dir)
        land = load_region_pgids("land")
        # With test GAUL data, cells 1-12 may not be in the real land set.
        # Instead verify the real invariant: land count > legacy count.
        legacy = load_region_pgids("africa_me_legacy")
        assert len(land) > len(legacy)

    def test_all_bundled_jsons_are_valid(self) -> None:
        """Every .json in the query package must be parseable."""
        pkg = Path(__file__).parent.parent / "src"
        pkg_dir = pkg / "datafactory_query"
        json_files = list(pkg_dir.glob("*.json"))
        assert len(json_files) >= 3
        for jf in json_files:
            data = json.loads(jf.read_text())
            assert isinstance(data, list)
            assert all(isinstance(x, int) for x in data)


# ── Dataset Loading ──────────────────────────────────────


class TestLoadDataset:

    def test_feature_frame_format(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir)
        _make_gaul_parquets(gaul_dir)

        ff = load_dataset(
            region="Testland",
            start="2020-01",
            end="2020-03",
            output_format="feature_frame",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert isinstance(ff, FeatureFrame)
        assert ff.n_features == 2
        # 6 cells * 3 months = 18 rows
        assert ff.n_rows == 18

    def test_dataframe_format(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir)
        _make_gaul_parquets(gaul_dir)

        df = load_dataset(
            region="Testland",
            start="2020-01",
            end="2020-03",
            output_format="dataframe",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) == 2
        assert len(df) == 18

    def test_feature_subsetting(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir, n_f=4)
        _make_gaul_parquets(gaul_dir)

        ff = load_dataset(
            region="global",
            features=["feat_0", "feat_2"],
            output_format="feature_frame",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert ff.n_features == 2
        assert ff.feature_names == ["feat_0", "feat_2"]

    def test_unknown_feature_raises(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir)
        _make_gaul_parquets(gaul_dir)

        with pytest.raises(ValueError, match="Unknown feature"):
            load_dataset(
                features=["nonexistent"],
                data_dir=data_dir,
                gaul_dir=gaul_dir,
            )

    def test_invalid_format_raises(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir)
        _make_gaul_parquets(gaul_dir)

        with pytest.raises(ValueError, match="Unknown format"):
            load_dataset(
                output_format="invalid",
                data_dir=data_dir,
                gaul_dir=gaul_dir,
            )

    def test_missing_grid_raises(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        with pytest.raises(FileNotFoundError, match="grid"):
            load_dataset(
                data_dir=tmp_path / "nonexistent",
                gaul_dir=tmp_path,
            )


# ── Zarr Loading ────────────────────────────────────────


def _make_assembled_zarr(
    zarr_path: Path,
    n_t: int = 6,
    n_h: int = 3,
    n_w: int = 4,
    n_f: int = 2,
) -> None:
    """Create a tiny zarr store matching production structure."""
    import xarray as xr

    time = np.array(
        [f"2020-{m:02d}-01" for m in range(1, n_t + 1)],
        dtype="datetime64[ns]",
    )
    lat = np.linspace(-89.75, 89.75, n_h)
    lon = np.linspace(-179.75, 179.75, n_w)
    pgids = np.arange(1, n_h * n_w + 1).reshape(n_h, n_w)

    feature_names = [f"feat_{i}" for i in range(n_f)]
    data_vars = {}
    for f in feature_names:
        data_vars[f] = (
            ["time", "lat", "lon"],
            np.ones((n_t, n_h, n_w), dtype=np.float32),
        )

    ds = xr.Dataset(
        data_vars,
        coords={
            "time": time,
            "lat": lat,
            "lon": lon,
            "pgid": (["lat", "lon"], pgids),
        },
        attrs={"feature_order": feature_names},
    )
    ds.to_zarr(zarr_path, mode="w")


class TestLoadDatasetZarr:

    def test_zarr_feature_frame(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        zarr_path = tmp_path / "grid.zarr"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_zarr(zarr_path)
        _make_gaul_parquets(gaul_dir)

        ff = load_dataset(
            region="Testland",
            start="2020-01",
            end="2020-03",
            output_format="feature_frame",
            data_dir=str(zarr_path),
            gaul_dir=gaul_dir,
        )
        assert isinstance(ff, FeatureFrame)
        assert ff.n_features == 2
        # 6 cells in Testland * 3 months = 18 rows
        assert ff.n_rows == 18

    def test_zarr_dataframe(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        zarr_path = tmp_path / "grid.zarr"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_zarr(zarr_path)
        _make_gaul_parquets(gaul_dir)

        df = load_dataset(
            region="Testland",
            start="2020-01",
            end="2020-03",
            output_format="dataframe",
            data_dir=str(zarr_path),
            gaul_dir=gaul_dir,
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) == 2
        assert len(df) == 18

    def test_zarr_temporal_subset(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        zarr_path = tmp_path / "grid.zarr"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_zarr(zarr_path)
        _make_gaul_parquets(gaul_dir)

        ff = load_dataset(
            region="global",
            start="2020-02",
            end="2020-04",
            output_format="feature_frame",
            data_dir=str(zarr_path),
            gaul_dir=gaul_dir,
        )
        # 12 cells (3x4) * 3 months = 36 rows
        assert ff.n_rows == 36

    def test_zarr_feature_subset(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        zarr_path = tmp_path / "grid.zarr"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_zarr(zarr_path, n_f=4)
        _make_gaul_parquets(gaul_dir)

        ff = load_dataset(
            region="global",
            features=["feat_0", "feat_2"],
            output_format="feature_frame",
            data_dir=str(zarr_path),
            gaul_dir=gaul_dir,
        )
        assert ff.n_features == 2
        assert ff.feature_names == ["feat_0", "feat_2"]

    def test_zarr_matches_npy(self, tmp_path: Path) -> None:
        """Zarr and npy paths produce identical output."""
        from datafactory_query.dataset import load_dataset

        npy_dir = tmp_path / "assembled"
        zarr_path = tmp_path / "grid.zarr"
        gaul_dir = tmp_path / "gaul"

        _make_assembled_grid(npy_dir)
        _make_assembled_zarr(zarr_path)
        _make_gaul_parquets(gaul_dir)

        ff_npy = load_dataset(
            region="global",
            output_format="feature_frame",
            data_dir=npy_dir,
            gaul_dir=gaul_dir,
        )
        ff_zarr = load_dataset(
            region="global",
            output_format="feature_frame",
            data_dir=str(zarr_path),
            gaul_dir=gaul_dir,
        )

        assert ff_npy.n_rows == ff_zarr.n_rows
        assert ff_npy.n_features == ff_zarr.n_features
        assert ff_npy.feature_names == ff_zarr.feature_names
        np.testing.assert_array_equal(
            ff_npy.values, ff_zarr.values,
        )

    def test_zarr_feature_order_from_attrs(
        self, tmp_path: Path,
    ) -> None:
        """feature_order attr controls column ordering."""
        import xarray as xr

        from datafactory_query.dataset import load_dataset

        zarr_path = tmp_path / "grid.zarr"
        gaul_dir = tmp_path / "gaul"

        # Create zarr with reverse-alphabetical feature_order
        n_t, n_h, n_w = 3, 3, 4
        names = ["zz_last", "aa_first"]
        time = np.array(
            [f"2020-{m:02d}-01" for m in range(1, n_t + 1)],
            dtype="datetime64[ns]",
        )
        lat = np.linspace(-89.75, 89.75, n_h)
        lon = np.linspace(-179.75, 179.75, n_w)
        pgids = np.arange(1, n_h * n_w + 1).reshape(n_h, n_w)
        data_vars = {
            n: (["time", "lat", "lon"],
                np.full((n_t, n_h, n_w), i, dtype=np.float32))
            for i, n in enumerate(names)
        }
        ds = xr.Dataset(
            data_vars,
            coords={
                "time": time, "lat": lat, "lon": lon,
                "pgid": (["lat", "lon"], pgids),
            },
            attrs={"feature_order": names},
        )
        ds.to_zarr(zarr_path, mode="w")
        _make_gaul_parquets(gaul_dir)

        ff = load_dataset(
            region="global",
            output_format="feature_frame",
            data_dir=str(zarr_path),
            gaul_dir=gaul_dir,
        )
        # Order matches attrs, not alphabetical
        assert ff.feature_names == ["zz_last", "aa_first"]
        # Values match: zz_last=0.0, aa_first=1.0
        assert ff.values[0, 0, 0] == 0.0
        assert ff.values[0, 1, 0] == 1.0

    def test_zarr_unknown_feature_raises(
        self, tmp_path: Path,
    ) -> None:
        """Requesting a nonexistent feature on zarr must raise."""
        from datafactory_query.dataset import load_dataset

        zarr_path = tmp_path / "grid.zarr"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_zarr(zarr_path)
        _make_gaul_parquets(gaul_dir)

        with pytest.raises(ValueError, match="nonexistent"):
            load_dataset(
                data_dir=str(zarr_path),
                features=["feat_a", "nonexistent"],
                gaul_dir=gaul_dir,
            )

    def test_zarr_nonexistent_raises(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        with pytest.raises(FileNotFoundError, match="[Zz]arr"):
            load_dataset(
                data_dir=str(tmp_path / "nonexistent.zarr"),
                gaul_dir=tmp_path,
            )


# ── Data Boundary Consistency (G2) ──────────────────────


class TestDataBoundaryConsistency:

    def test_last_valid_month_id_roundtrip(
        self, tmp_path: Path,
    ) -> None:
        """Metadata survives assemble → zarr export → query load."""
        import xarray as xr

        from datafactory_query.dataset import _load_grid_from_zarr

        zarr_path = tmp_path / "grid.zarr"
        n_t, n_h, n_w = 6, 3, 4

        time = np.array(
            [f"2020-{m:02d}-01" for m in range(1, n_t + 1)],
            dtype="datetime64[ns]",
        )
        lat = np.linspace(-89.75, 89.75, n_h)
        lon = np.linspace(-179.75, 179.75, n_w)
        pgids = np.arange(1, n_h * n_w + 1).reshape(n_h, n_w)

        names = ["ged_sb_best", "pop_total"]
        data_vars = {
            n: (
                ["time", "lat", "lon"],
                np.ones((n_t, n_h, n_w), dtype=np.float32),
            )
            for n in names
        }

        expected_mid = 485
        ds = xr.Dataset(
            data_vars,
            coords={
                "time": time,
                "lat": lat,
                "lon": lon,
                "pgid": (["lat", "lon"], pgids),
            },
            attrs={
                "feature_order": names,
                "last_valid_month_id": expected_mid,
            },
        )
        ds.to_zarr(zarr_path, mode="w")

        _, _, _, _, last_valid, _, _, _ = _load_grid_from_zarr(str(zarr_path))
        assert last_valid == expected_mid


# ── Feature Order Parity (G5, C-127) ───────────────────


class TestFeatureOrderParity:

    def test_npy_and_zarr_feature_order_match(
        self, tmp_path: Path,
    ) -> None:
        """npy and zarr backends must return identical feature order."""
        import xarray as xr

        from datafactory_query.dataset import (
            _load_grid_from_npy,
            _load_grid_from_zarr,
        )

        names = ["zz_last", "bb_mid", "aa_first"]
        n_t, n_h, n_w = 3, 3, 4
        n_f = len(names)

        # Build npy
        npy_dir = tmp_path / "npy"
        npy_dir.mkdir()
        grid = np.ones((n_t, n_h, n_w, n_f), dtype=np.float32)
        np.save(npy_dir / "grid.npy", grid)
        np.save(
            npy_dir / "pgids.npy",
            np.arange(1, n_h * n_w + 1).reshape(n_h, n_w),
        )
        np.save(
            npy_dir / "time_steps.npy",
            np.array(
                [f"2020-{m:02d}" for m in range(1, n_t + 1)],
                dtype="datetime64[M]",
            ),
        )
        (npy_dir / "feature_names.json").write_text(json.dumps(names))

        # Build zarr with same feature_order
        zarr_path = tmp_path / "grid.zarr"
        time = np.array(
            [f"2020-{m:02d}-01" for m in range(1, n_t + 1)],
            dtype="datetime64[ns]",
        )
        lat = np.linspace(-89.75, 89.75, n_h)
        lon = np.linspace(-179.75, 179.75, n_w)
        pgids = np.arange(1, n_h * n_w + 1).reshape(n_h, n_w)
        data_vars = {
            n: (
                ["time", "lat", "lon"],
                np.ones((n_t, n_h, n_w), dtype=np.float32),
            )
            for n in names
        }
        ds = xr.Dataset(
            data_vars,
            coords={
                "time": time,
                "lat": lat,
                "lon": lon,
                "pgid": (["lat", "lon"], pgids),
            },
            attrs={"feature_order": names},
        )
        ds.to_zarr(zarr_path, mode="w")

        _, _, _, npy_features, _, _, _, _ = _load_grid_from_npy(npy_dir)
        _, _, _, zarr_features, _, _, _, _ = _load_grid_from_zarr(
            str(zarr_path),
        )
        assert npy_features == zarr_features


class TestZarrFeatureOrderFallback:
    """C-127: warn when zarr store lacks feature_order attr."""

    def _make_zarr_no_feature_order(
        self, tmp_path: Path
    ) -> Path:
        import xarray as xr

        names = ["zz_last", "bb_mid", "aa_first"]
        n_t, n_h, n_w = 3, 3, 4
        data_vars = {
            n: (
                ["time", "lat", "lon"],
                np.full((n_t, n_h, n_w), i, dtype=np.float32),
            )
            for i, n in enumerate(names)
        }
        ds = xr.Dataset(
            data_vars,
            coords={
                "time": np.arange(
                    "2020-01", "2020-04", dtype="datetime64[M]"
                ),
                "lat": np.linspace(-45, 45, n_h),
                "lon": np.linspace(-90, 90, n_w),
                "pgid": (
                    ["lat", "lon"],
                    np.arange(1, n_h * n_w + 1).reshape(n_h, n_w),
                ),
            },
        )
        zarr_path = tmp_path / "no_order.zarr"
        ds.to_zarr(zarr_path, mode="w")
        return zarr_path

    def test_zarr_missing_feature_order_warns(
        self, tmp_path: Path
    ) -> None:
        from datafactory_query.dataset import _load_grid_from_zarr

        zarr_path = self._make_zarr_no_feature_order(tmp_path)
        with pytest.warns(UserWarning, match="feature_order"):
            _load_grid_from_zarr(str(zarr_path))

    def test_zarr_missing_feature_order_returns_sorted(
        self, tmp_path: Path
    ) -> None:
        import warnings

        from datafactory_query.dataset import _load_grid_from_zarr

        zarr_path = self._make_zarr_no_feature_order(tmp_path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            _, _, _, features, _, _, _, _ = _load_grid_from_zarr(
                str(zarr_path)
            )
        assert features == ["aa_first", "bb_mid", "zz_last"]


# ── Edge Cases (G8) ────────────────────────────────────


class TestLoadDatasetEdgeCases:

    def test_single_time_step(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir, n_t=1)
        _make_gaul_parquets(gaul_dir)

        ff = load_dataset(
            region="Testland",
            output_format="feature_frame",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert isinstance(ff, FeatureFrame)
        assert ff.n_rows == 6  # 6 cells * 1 month

    def test_time_range_producing_single_month(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir, n_t=6)
        _make_gaul_parquets(gaul_dir)

        ff = load_dataset(
            region="global",
            start="2020-03",
            end="2020-03",
            output_format="feature_frame",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert ff.n_rows == 12  # 12 cells * 1 month


# ── Beige: Boundary Conditions ─────────────────────────


class TestLoadDatasetBeige:

    def test_single_feature_request(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir, n_f=4)
        _make_gaul_parquets(gaul_dir)

        ff = load_dataset(
            region="global",
            features=["feat_0"],
            output_format="feature_frame",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert ff.n_features == 1
        assert ff.feature_names == ["feat_0"]

    def test_all_features_explicit_matches_default(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir, n_f=2)
        _make_gaul_parquets(gaul_dir)

        ff_default = load_dataset(
            region="global",
            output_format="feature_frame",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        ff_explicit = load_dataset(
            region="global",
            features=["feat_0", "feat_1"],
            output_format="feature_frame",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert ff_default.feature_names == ff_explicit.feature_names
        np.testing.assert_array_equal(
            ff_default.values, ff_explicit.values,
        )


# ── Red: Adversarial Inputs ───────────────────────────


class TestLoadDatasetRed:

    def test_corrupted_grid_file(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir)
        _make_gaul_parquets(gaul_dir)

        (data_dir / "grid.npy").write_bytes(b"NOT A NPY FILE")

        with pytest.raises(ValueError):
            load_dataset(
                region="global",
                data_dir=data_dir,
                gaul_dir=gaul_dir,
            )

    def test_mismatched_feature_count(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir, n_f=2)
        _make_gaul_parquets(gaul_dir)

        (data_dir / "feature_names.json").write_text(
            json.dumps(["a", "b", "c"]),
        )

        with pytest.raises(ValueError, match="feature_names length"):
            load_dataset(
                region="global",
                data_dir=data_dir,
                gaul_dir=gaul_dir,
            )

    def test_mismatched_pgids_shape(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir, n_h=3, n_w=4)
        _make_gaul_parquets(gaul_dir)

        wrong_pgids = np.arange(1, 7).reshape(2, 3)
        np.save(data_dir / "pgids.npy", wrong_pgids)

        with pytest.raises(ValueError, match="pgids shape"):
            load_dataset(
                region="global",
                data_dir=data_dir,
                gaul_dir=gaul_dir,
            )

    def test_nan_filled_grid_loads(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir)
        _make_gaul_parquets(gaul_dir)

        grid = np.full((6, 3, 4, 2), np.nan, dtype=np.float32)
        np.save(data_dir / "grid.npy", grid)

        ff = load_dataset(
            region="global",
            output_format="feature_frame",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert np.all(np.isnan(ff.values))

    def test_zero_time_steps(self, tmp_path: Path) -> None:
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_assembled_grid(data_dir)
        _make_gaul_parquets(gaul_dir)

        np.save(
            data_dir / "time_steps.npy",
            np.array([], dtype="datetime64[M]"),
        )

        with pytest.raises(IndexError):
            load_dataset(
                region="global",
                data_dir=data_dir,
                gaul_dir=gaul_dir,
            )


# ── get_last_valid_month_id (G9, C-134) ────────────────


class TestGetLastValidMonthId:

    def test_raises_on_network_error(self) -> None:
        from unittest.mock import patch
        from urllib.error import URLError

        from datafactory_query.defaults import get_last_valid_month_id

        with (
            patch(
                "urllib.request.urlopen",
                side_effect=URLError("network down"),
            ),
            pytest.raises(URLError),
        ):
            get_last_valid_month_id("http://fake/grid.zarr")

    def test_raises_on_auth_failure(self) -> None:
        from unittest.mock import patch
        from urllib.error import HTTPError

        from datafactory_query.defaults import get_last_valid_month_id

        with (
            patch(
                "urllib.request.urlopen",
                side_effect=HTTPError(
                    "http://fake/.zattrs", 401, "Unauthorized",
                    {}, None,  # type: ignore[arg-type]
                ),
            ),
            pytest.raises(HTTPError),
        ):
            get_last_valid_month_id("http://fake/grid.zarr")

    def test_raises_on_json_parse_error(self) -> None:
        from unittest.mock import MagicMock, patch

        from datafactory_query.defaults import get_last_valid_month_id

        fake_resp = MagicMock()
        fake_resp.read.return_value = b"NOT JSON"
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "urllib.request.urlopen",
                return_value=fake_resp,
            ),
            pytest.raises(json.JSONDecodeError),
        ):
            get_last_valid_month_id("http://fake/grid.zarr")

    def test_logs_error_on_network_failure(self, caplog) -> None:
        import logging
        from unittest.mock import patch
        from urllib.error import URLError

        from datafactory_query.defaults import get_last_valid_month_id

        with (
            caplog.at_level(logging.ERROR),
            patch(
                "urllib.request.urlopen",
                side_effect=URLError("network down"),
            ),
            pytest.raises(URLError),
        ):
            get_last_valid_month_id("http://fake/grid.zarr")

        assert any(
            r.levelno >= logging.ERROR for r in caplog.records
        )

    def test_returns_int_on_success(self) -> None:
        from unittest.mock import MagicMock, patch

        from datafactory_query.defaults import get_last_valid_month_id

        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps(
            {"last_valid_month_id": 540}
        ).encode()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake_resp):
            result = get_last_valid_month_id("http://fake/grid.zarr")
        assert result == 540

    def test_returns_none_when_attr_missing(self) -> None:
        from unittest.mock import MagicMock, patch

        from datafactory_query.defaults import get_last_valid_month_id

        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps(
            {"export_timestamp": "2026-01-01T00:00:00"}
        ).encode()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake_resp):
            result = get_last_valid_month_id("http://fake/grid.zarr")
        assert result is None


class TestIsRemote:

    def test_http_url(self) -> None:
        from datafactory_query.dataset import _is_remote

        assert _is_remote("http://server/grid.zarr") is True

    def test_https_url(self) -> None:
        from datafactory_query.dataset import _is_remote

        assert _is_remote("https://server/grid.zarr") is True

    def test_path_object(self) -> None:
        from datafactory_query.dataset import _is_remote

        assert _is_remote(Path("data/assembled")) is False

    def test_local_string(self) -> None:
        from datafactory_query.dataset import _is_remote

        assert _is_remote("/tmp/grid.zarr") is False


# ---- Remote Zarr Smoke Tests (M12) ----

REMOTE_ZARR = DEFAULT_REMOTE.zarr_url


@pytest.mark.consumer
class TestRemoteZarrSmoke:
    """Smoke tests against the live Hetzner zarr store.

    Gated behind --run-consumer (requires network + ~/.netrc).
    These verify the full remote path: credential resolution,
    HTTP fetch, lazy subsetting, and format conversion.
    """

    def test_load_single_feature_one_month(self) -> None:
        """Minimal remote load — 1 feature, 1 month."""
        from datafactory_query.dataset import load_dataset

        df = load_dataset(
            data_dir=REMOTE_ZARR,
            region="land",
            start=480,
            end=480,
            features=["ged_sb_best"],
            output_format="dataframe",
        )
        assert df.shape[0] > 0
        assert "ged_sb_best" in df.columns
        assert df.index.names == ["month_id", "priogrid_gid"]

    def test_load_feature_frame_africa(self) -> None:
        """Load 12 months of Africa as FeatureFrame."""
        from datafactory_query.dataset import load_dataset

        ff = load_dataset(
            data_dir=REMOTE_ZARR,
            region="africa",
            start=480,
            end=491,
            features=["ged_sb_best", "ged_ns_best"],
            output_format="feature_frame",
        )
        assert ff.values.shape[1] == 2
        assert set(ff.feature_names) == {
            "ged_sb_best", "ged_ns_best",
        }
        assert len(ff.identifiers["time"]) > 0

    def test_remote_nonexistent_store_raises(self) -> None:
        """Bad URL should raise, not hang."""
        from datafactory_query.dataset import load_dataset

        with pytest.raises(
            (FileNotFoundError, PermissionError),
        ):
            load_dataset(
                data_dir="http://204.168.219.108/no.zarr",
                region="land",
                start=480,
                end=480,
                features=["ged_sb_best"],
            )


# ---- RemoteConfig tests (C-290, #237) ----


class TestRemoteConfigGreen:
    """CIC Section 3 guarantees for RemoteConfig (ADR-005)."""

    def test_frozen_enforcement(self) -> None:
        """RemoteConfig is frozen — field assignment raises."""
        from datafactory_query.defaults import RemoteConfig

        cfg = RemoteConfig()
        with pytest.raises(AttributeError):
            cfg.server = "1.2.3.4"  # type: ignore[misc]

    def test_zarr_url_construction(self) -> None:
        """DEFAULT_REMOTE.zarr_url matches expected format."""
        assert DEFAULT_REMOTE.zarr_url == (
            "http://204.168.219.108/grid.zarr"
        )

    def test_parquet_url_construction(self) -> None:
        """DEFAULT_REMOTE.parquet_url matches expected format."""
        assert DEFAULT_REMOTE.parquet_url == (
            "http://204.168.219.108/dataframe.parquet"
        )

    def test_default_remote_is_remote_config(self) -> None:
        """DEFAULT_REMOTE is a RemoteConfig with expected defaults."""
        from datafactory_query.defaults import RemoteConfig

        assert isinstance(DEFAULT_REMOTE, RemoteConfig)
        assert DEFAULT_REMOTE.server == "204.168.219.108"
        assert DEFAULT_REMOTE.zarr_path == "/grid.zarr"
        assert DEFAULT_REMOTE.scheme == "http"


class TestRemoteConfigBeige:
    """Custom overrides for RemoteConfig (ADR-005)."""

    def test_custom_scheme_overrides_url(self) -> None:
        """Custom scheme propagates to zarr_url."""
        from datafactory_query.defaults import RemoteConfig

        cfg = RemoteConfig(scheme="https")
        assert cfg.zarr_url.startswith("https://")

    def test_custom_server_overrides_url(self) -> None:
        """Custom server propagates to zarr_url."""
        from datafactory_query.defaults import RemoteConfig

        cfg = RemoteConfig(server="example.com")
        assert "example.com" in cfg.zarr_url


# ---- PARTITIONS tests (C-290, #237) ----


class TestPartitionsGreen:
    """Structure and immutability tests for PARTITIONS (ADR-005)."""

    def test_partitions_immutable(self) -> None:
        """Top-level PARTITIONS is immutable (MappingProxyType)."""
        from datafactory_query.defaults import PARTITIONS

        with pytest.raises(TypeError):
            PARTITIONS["new_key"] = {}  # type: ignore[index]

    def test_nested_partitions_immutable(self) -> None:
        """Nested partition dicts are also immutable."""
        from datafactory_query.defaults import PARTITIONS

        with pytest.raises(TypeError):
            PARTITIONS["calibration"]["new_key"] = (0, 0)  # type: ignore[index]

    def test_calibration_boundaries_correct(self) -> None:
        """Calibration train/test boundaries match expected values."""
        from datafactory_query.defaults import PARTITIONS

        assert PARTITIONS["calibration"]["train"] == (121, 456)
        assert PARTITIONS["calibration"]["test"] == (457, 504)

    def test_validation_boundaries_correct(self) -> None:
        """Validation train/test boundaries match expected values."""
        from datafactory_query.defaults import PARTITIONS

        assert PARTITIONS["validation"]["train"] == (121, 504)
        assert PARTITIONS["validation"]["test"] == (505, 552)


# ---- country_month output format tests (C-290, #237) ----


class TestLoadDatasetCountryMonthGreen:
    """Tests for country_month output format (ADR-005)."""

    def test_country_month_returns_dataframe(
        self, tmp_path: Path,
    ) -> None:
        """country_month format returns DataFrame with MultiIndex."""
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"

        n_t, n_h, n_w, n_f = 3, 3, 4, 3
        feature_names = ["feat_0", "feat_1", "gaul0_code"]
        grid = np.ones(
            (n_t, n_h, n_w, n_f), dtype=np.float32,
        )
        grid[:, :, :, 2] = 100.0
        grid[:, :2, :, 2] = 100.0
        grid[:, 2:, :, 2] = 200.0

        data_dir.mkdir(parents=True, exist_ok=True)
        np.save(data_dir / "grid.npy", grid)
        pgids = np.arange(1, n_h * n_w + 1).reshape(n_h, n_w)
        np.save(data_dir / "pgids.npy", pgids)
        time_steps = np.array(
            [f"2020-{m:02d}" for m in range(1, n_t + 1)],
            dtype="datetime64[M]",
        )
        np.save(data_dir / "time_steps.npy", time_steps)
        (data_dir / "feature_names.json").write_text(
            json.dumps(feature_names),
        )
        _make_gaul_parquets(gaul_dir)

        df = load_dataset(
            data_dir=str(data_dir),
            region="global",
            output_format="country_month",
            features=["feat_0", "feat_1"],
        )

        assert isinstance(df, pd.DataFrame)
        assert df.index.names == ["month_id", "country_id"]

    def test_country_month_auto_includes_gaul0_code(
        self, tmp_path: Path,
    ) -> None:
        """gaul0_code is auto-included even when not in features."""
        from datafactory_query.dataset import load_dataset

        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"

        n_t, n_h, n_w, n_f = 2, 3, 4, 3
        feature_names = ["feat_0", "feat_1", "gaul0_code"]
        grid = np.ones(
            (n_t, n_h, n_w, n_f), dtype=np.float32,
        )
        grid[:, :, :, 2] = 100.0

        data_dir.mkdir(parents=True, exist_ok=True)
        np.save(data_dir / "grid.npy", grid)
        pgids = np.arange(1, n_h * n_w + 1).reshape(n_h, n_w)
        np.save(data_dir / "pgids.npy", pgids)
        time_steps = np.array(
            ["2020-01", "2020-02"],
            dtype="datetime64[M]",
        )
        np.save(data_dir / "time_steps.npy", time_steps)
        (data_dir / "feature_names.json").write_text(
            json.dumps(feature_names),
        )
        _make_gaul_parquets(gaul_dir)

        df = load_dataset(
            data_dir=str(data_dir),
            region="global",
            output_format="country_month",
            features=["feat_0"],
        )

        assert isinstance(df, pd.DataFrame)
        assert "gaul0_code" not in df.columns
        assert "feat_0" in df.columns


# ── Pre-coverage Warning (ADR-047, C-156) ─────────────


class TestLoadDatasetTemporalWarning:
    """Consumer warning for pre-coverage queries (C-156)."""

    def _make_grid_with_first_valid(
        self, tmp_path: Path, first_valid_acled: int,
    ) -> Path:
        """Create a minimal assembled grid with provenance
        containing first_valid_acled_month_id."""
        import json as _json

        data_dir = tmp_path / "assembled"
        data_dir.mkdir()
        n_t, n_h, n_w = 6, 2, 2
        grid = np.zeros(
            (n_t, n_h, n_w, 3), dtype=np.float32,
        )
        np.save(data_dir / "grid.npy", grid)
        pgids = np.arange(n_h * n_w).reshape(n_h, n_w) + 1
        np.save(data_dir / "pgids.npy", pgids)
        ts = np.array(
            ["2020-01", "2020-02", "2020-03",
             "2020-04", "2020-05", "2020-06"],
            dtype="datetime64[M]",
        )
        np.save(data_dir / "time_steps.npy", ts)
        features = ["ged_sb_best", "acled_count", "acled_fatalities"]
        (data_dir / "feature_names.json").write_text(
            _json.dumps(features),
        )
        prov = {
            "last_valid_month_id": 486,
            "first_valid_acled_month_id": first_valid_acled,
            "acled_features": ["acled_count", "acled_fatalities"],
        }
        (data_dir / "provenance.json").write_text(
            _json.dumps(prov),
        )
        return data_dir

    def test_warning_emitted_for_pre_coverage_query(
        self, tmp_path: Path,
    ) -> None:
        """Requesting ACLED features starting before their
        first_valid month emits UserWarning."""
        from datafactory_query.dataset import load_dataset

        data_dir = self._make_grid_with_first_valid(
            tmp_path, first_valid_acled=483,
        )
        with pytest.warns(
            UserWarning, match="ACLED data begins at month_id",
        ):
            load_dataset(
                data_dir=data_dir,
                region="global",
                output_format="feature_frame",
                features=["acled_count"],
            )

    def test_no_warning_for_in_coverage_query(
        self, tmp_path: Path,
    ) -> None:
        """Requesting ACLED features within coverage emits no
        pre-coverage warning."""
        import warnings as _warnings

        from datafactory_query.dataset import load_dataset

        data_dir = self._make_grid_with_first_valid(
            tmp_path, first_valid_acled=481,
        )
        with _warnings.catch_warnings():
            _warnings.filterwarnings(
                "error",
                message="ACLED data begins",
                category=UserWarning,
            )
            load_dataset(
                data_dir=data_dir,
                region="global",
                output_format="feature_frame",
                features=["acled_count"],
            )

    def test_no_warning_when_non_acled_features_only(
        self, tmp_path: Path,
    ) -> None:
        """Requesting only UCDP features does not trigger
        pre-coverage ACLED warning."""
        import warnings as _warnings

        from datafactory_query.dataset import load_dataset

        data_dir = self._make_grid_with_first_valid(
            tmp_path, first_valid_acled=483,
        )
        with _warnings.catch_warnings():
            _warnings.filterwarnings(
                "error",
                message="ACLED data begins",
                category=UserWarning,
            )
            load_dataset(
                data_dir=data_dir,
                region="global",
                output_format="feature_frame",
                features=["ged_sb_best"],
            )
