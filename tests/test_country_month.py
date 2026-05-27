"""Tests for country-month aggregation adapter and load_dataset integration.

Verifies that grid_to_country_month() correctly sums grid-cell
features by (month_id, country_id), and that load_dataset() exposes
the country_month output format end-to-end.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_adapters.grid_to_country_month import grid_to_country_month


def _synthetic_grid(
    n_t: int = 3,
    n_h: int = 4,
    n_w: int = 5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Build a small synthetic grid with two known countries.

    Country A (code 10): top two rows (h=0,1) — 10 cells
    Country B (code 20): bottom two rows (h=2,3) — 10 cells
    Feature ged_sb_best: value = 1.0 everywhere
    Feature ged_ns_best: value = 2.0 everywhere
    Feature gaul0_code:  10 for top rows, 20 for bottom rows
    """
    features = ["ged_sb_best", "ged_ns_best", "gaul0_code"]
    grid = np.zeros((n_t, n_h, n_w, len(features)), dtype=np.float32)
    grid[:, :, :, 0] = 1.0  # ged_sb_best
    grid[:, :, :, 1] = 2.0  # ged_ns_best
    grid[:, 0:2, :, 2] = 10  # country A
    grid[:, 2:4, :, 2] = 20  # country B

    pgids = np.arange(1, n_h * n_w + 1).reshape(n_h, n_w)
    time_steps = np.array(
        [f"2020-{m:02d}" for m in range(1, n_t + 1)],
        dtype="datetime64[M]",
    )
    return grid, pgids, time_steps, features


class TestGridToCountryMonth:

    def test_index_names(self) -> None:
        grid, pgids, ts, feats = _synthetic_grid()
        df = grid_to_country_month(grid, pgids, ts, feats)
        assert df.index.names == ["month_id", "country_id"]

    def test_country_feature_excluded(self) -> None:
        grid, pgids, ts, feats = _synthetic_grid()
        df = grid_to_country_month(grid, pgids, ts, feats)
        assert "gaul0_code" not in df.columns

    def test_correct_sums(self) -> None:
        grid, pgids, ts, feats = _synthetic_grid()
        df = grid_to_country_month(grid, pgids, ts, feats)
        # Country A has 2 rows * 5 cols = 10 cells, ged_sb=1.0 each
        month_id_jan = df.index.get_level_values("month_id")[0]
        assert df.loc[(month_id_jan, 10), "ged_sb_best"] == 10.0
        assert df.loc[(month_id_jan, 10), "ged_ns_best"] == 20.0
        # Country B: same cell count
        assert df.loc[(month_id_jan, 20), "ged_sb_best"] == 10.0
        assert df.loc[(month_id_jan, 20), "ged_ns_best"] == 20.0

    def test_correct_number_of_rows(self) -> None:
        grid, pgids, ts, feats = _synthetic_grid(n_t=3)
        df = grid_to_country_month(grid, pgids, ts, feats)
        # 3 months * 2 countries = 6 rows
        assert len(df) == 6

    def test_ocean_excluded(self) -> None:
        grid, pgids, ts, feats = _synthetic_grid()
        # Set bottom row to ocean (gaul0_code = 0)
        grid[:, 3, :, 2] = 0
        with pytest.warns(UserWarning, match="unmapped GAUL"):
            df = grid_to_country_month(grid, pgids, ts, feats)
        countries = df.index.get_level_values("country_id").unique()
        assert 0 not in countries
        # Country B now has only 1 row = 5 cells
        month_id_jan = df.index.get_level_values("month_id")[0]
        assert df.loc[(month_id_jan, 20), "ged_sb_best"] == 5.0

    def test_sorted_index(self) -> None:
        grid, pgids, ts, feats = _synthetic_grid()
        df = grid_to_country_month(grid, pgids, ts, feats)
        assert df.index.is_monotonic_increasing

    def test_missing_country_feature_raises(self) -> None:
        grid, pgids, ts, _ = _synthetic_grid()
        with pytest.raises(ValueError, match="Country feature"):
            grid_to_country_month(
                grid, pgids, ts, ["a", "b", "c"],
                country_feature="nonexistent",
            )

    def test_warns_on_excluded_cells_with_events(self) -> None:
        """C-149: excluded cells with nonzero events must trigger warning."""
        grid, pgids, ts, feats = _synthetic_grid()
        # Set one row to unmapped (gaul0_code = -1) but keep event values
        grid[:, 3, :, 2] = -1
        with pytest.warns(UserWarning, match="unmapped GAUL"):
            grid_to_country_month(grid, pgids, ts, feats)

    def test_no_warning_when_excluded_cells_all_zero(self) -> None:
        """No warning when excluded cells have zero event values."""
        grid, pgids, ts, feats = _synthetic_grid()
        # Set one row to ocean (gaul0_code = 0) AND zero out events
        grid[:, 3, :, 2] = 0
        grid[:, 3, :, 0] = 0.0  # ged_sb_best
        grid[:, 3, :, 1] = 0.0  # ged_ns_best
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            grid_to_country_month(grid, pgids, ts, feats)

    def test_land_pgids_filter(self) -> None:
        grid, pgids, ts, feats = _synthetic_grid()
        # Only include pgids 1-5 (first row = country A)
        land = set(range(1, 6))
        df = grid_to_country_month(
            grid, pgids, ts, feats, land_pgids=land,
        )
        countries = df.index.get_level_values("country_id").unique()
        assert list(countries) == [10]
        month_id_jan = df.index.get_level_values("month_id")[0]
        assert df.loc[(month_id_jan, 10), "ged_sb_best"] == 5.0


def _make_assembled_dir(
    tmp_path: Path,
    n_t: int = 3,
) -> tuple[Path, Path]:
    """Create assembled grid + GAUL files for integration tests."""
    grid, pgids, ts, feats = _synthetic_grid(n_t=n_t)

    data_dir = tmp_path / "assembled"
    data_dir.mkdir()
    np.save(data_dir / "grid.npy", grid)
    np.save(data_dir / "pgids.npy", pgids)
    np.save(data_dir / "time_steps.npy", ts)
    (data_dir / "feature_names.json").write_text(json.dumps(feats))

    gaul_dir = tmp_path / "gaul"
    gaul_dir.mkdir()
    n_cells = pgids.size
    gids = list(range(1, n_cells + 1))
    name_table = pa.table({
        "gid": gids,
        "value": ["Testland"] * n_cells,
    })
    pq.write_table(name_table, gaul_dir / "gaul0_name.parquet")
    code_table = pa.table({
        "gid": gids,
        "value": [10] * (n_cells // 2) + [20] * (n_cells // 2),
    })
    pq.write_table(code_table, gaul_dir / "gaul0_code.parquet")

    return data_dir, gaul_dir


class TestLoadDatasetCountryMonth:

    def test_load_returns_dataframe(self, tmp_path: Path) -> None:
        from datafactory_query import load_dataset

        data_dir, gaul_dir = _make_assembled_dir(tmp_path)
        df = load_dataset(
            region="land",
            output_format="country_month",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert isinstance(df, pd.DataFrame)
        assert df.index.names == ["month_id", "country_id"]

    def test_gaul0_auto_included(self, tmp_path: Path) -> None:
        """gaul0_code is auto-included even when not in features."""
        from datafactory_query import load_dataset

        data_dir, gaul_dir = _make_assembled_dir(tmp_path)
        df = load_dataset(
            region="land",
            features=["ged_sb_best"],
            output_format="country_month",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert "ged_sb_best" in df.columns
        assert "gaul0_code" not in df.columns

    def test_gaul0_not_in_output(self, tmp_path: Path) -> None:
        from datafactory_query import load_dataset

        data_dir, gaul_dir = _make_assembled_dir(tmp_path)
        df = load_dataset(
            region="land",
            output_format="country_month",
            data_dir=data_dir,
            gaul_dir=gaul_dir,
        )
        assert "gaul0_code" not in df.columns
