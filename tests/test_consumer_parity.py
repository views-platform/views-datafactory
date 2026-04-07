"""Consumer parity tests — three purple_alien clones.

Each clone loads data from the data factory in a different format
(DataFrame, FeatureFrame, zarr), transforms it to match purple_alien's
calibration parquet, and asserts parity.

Known discrepancy: ~0.05% of feature values differ because VIEWSER
uses ``ged_sb_best_sum_nokgi`` (filters imprecisely geolocated events)
while the data factory uses ``ged_sb_best`` (all events). The tests
assert structural parity (shape, index, row/col) exactly, and feature
parity within a 0.1% mismatch threshold.

Gated behind --run-consumer (requires assembled grid + reference parquet).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from datafactory_query import load_dataset

# ── Paths ────────────────────────────────────────────────
_DEFAULT_PARQUET = (
    Path(__file__).resolve().parents[1]
    / ".."
    / "views-models"
    / "models"
    / "purple_alien"
    / "data"
    / "raw"
    / "calibration_viewser_df.parquet"
)
PURPLE_ALIEN_PARQUET = Path(
    os.environ.get("PURPLE_ALIEN_PARQUET", str(_DEFAULT_PARQUET))
)
DATA_DIR = Path("data/assembled")
GAUL_DIR = Path("data/raw/gaul_admin")
ZARR_PATH = Path("data/assembled/grid.zarr")

# ── Feature mapping ──────────────────────────────────────
# data factory name -> purple alien name
FEATURE_RENAME = {
    "ged_sb_best": "lr_sb_best",
    "ged_ns_best": "lr_ns_best",
    "ged_os_best": "lr_os_best",
}
DF_FEATURES = list(FEATURE_RENAME.keys())
FEATURE_COLS = list(FEATURE_RENAME.values())

# ── Temporal bounds (calibration partition) ───────────────
MONTH_START = 121  # 1990-01
MONTH_END = 492  # 2018-12
MONTH_ID_EPOCH = 1980

# ── Parity columns (c_id excluded: GAUL != VIEWSER codes) ─
PARITY_COLS = ["col", "row", "lr_sb_best", "lr_ns_best", "lr_os_best"]

# Known discrepancy threshold: VIEWSER uses nokgi filter, we don't.
MAX_MISMATCH_RATE = 0.001  # 0.1%


# ── Helpers ──────────────────────────────────────────────


def build_parity_df(df: pd.DataFrame) -> pd.DataFrame:
    """Transform a data-factory DataFrame into purple_alien format.

    Selects the 3 GED features, renames to lr_* convention,
    derives row/col from pgid index, fills NaN with 0, and
    coerces to float64.
    """
    result = df[list(FEATURE_RENAME.keys())].rename(
        columns=FEATURE_RENAME,
    )

    pgids = result.index.get_level_values("priogrid_gid")
    result = result.copy()
    result["row"] = ((pgids - 1) // 720 + 1).astype(np.float64)
    result["col"] = ((pgids - 1) % 720 + 1).astype(np.float64)

    result = result.fillna(0.0)
    result = result[PARITY_COLS].astype(np.float64)
    return result.sort_index()


def assert_consumer_parity(
    result: pd.DataFrame,
    reference: pd.DataFrame,
) -> None:
    """Assert structural and feature parity between result and reference.

    Structural checks (row/col, shape, index) are exact.
    Feature checks allow up to MAX_MISMATCH_RATE discrepancy,
    reflecting the known nokgi filter difference.
    """
    # Shape
    assert result.shape == reference.shape, (
        f"Shape mismatch: {result.shape} vs {reference.shape}"
    )

    # Index values (ignoring int32/int64 dtype)
    assert (
        result.index.get_level_values("month_id").tolist()
        == reference.index.get_level_values("month_id").tolist()
    )
    assert (
        result.index.get_level_values("priogrid_gid").tolist()
        == reference.index.get_level_values("priogrid_gid").tolist()
    )

    # Row/col — exact (derived from pgid, deterministic)
    np.testing.assert_array_equal(
        result["row"].values, reference["row"].values,
    )
    np.testing.assert_array_equal(
        result["col"].values, reference["col"].values,
    )

    # Features — within mismatch threshold
    n_total = len(result)
    for col in FEATURE_COLS:
        diff = np.abs(result[col].values - reference[col].values)
        n_mismatch = (diff > 1e-5).sum()
        rate = n_mismatch / n_total
        assert rate <= MAX_MISMATCH_RATE, (
            f"{col}: {n_mismatch} mismatches ({rate:.4%}) "
            f"exceeds threshold {MAX_MISMATCH_RATE:.2%}"
        )


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture(scope="module")
def reference_df() -> pd.DataFrame:
    """Load the purple_alien ground truth, keeping only parity columns."""
    if not PURPLE_ALIEN_PARQUET.exists():
        pytest.skip(f"Reference parquet not found: {PURPLE_ALIEN_PARQUET}")
    df = pd.read_parquet(PURPLE_ALIEN_PARQUET)
    return df[PARITY_COLS].sort_index()


@pytest.fixture(scope="module")
def reference_pgids(reference_df: pd.DataFrame) -> set[int]:
    """Extract the exact set of pgids from the reference."""
    return set(
        reference_df.index.get_level_values("priogrid_gid").unique()
    )


# ── Clone 1: DataFrame consumer ─────────────────────────


@pytest.mark.consumer
class TestDataFrameConsumer:
    """Load via load_dataset(output_format='dataframe')."""

    def test_parity(
        self,
        reference_df: pd.DataFrame,
        reference_pgids: set[int],
    ) -> None:
        if not DATA_DIR.exists():
            pytest.skip(f"Assembled grid not found: {DATA_DIR}")

        df = load_dataset(
            region="land",
            start=MONTH_START,
            end=MONTH_END,
            features=DF_FEATURES,
            output_format="dataframe",
            data_dir=DATA_DIR,
            gaul_dir=GAUL_DIR,
            month_id_epoch=MONTH_ID_EPOCH,
        )

        mask = df.index.get_level_values("priogrid_gid").isin(
            reference_pgids,
        )
        df = df.loc[mask]
        result = build_parity_df(df)
        assert_consumer_parity(result, reference_df)


# ── Clone 2: FeatureFrame consumer ──────────────────────


@pytest.mark.consumer
class TestFeatureFrameConsumer:
    """Load via load_dataset(output_format='feature_frame')."""

    def test_parity(
        self,
        reference_df: pd.DataFrame,
        reference_pgids: set[int],
    ) -> None:
        if not DATA_DIR.exists():
            pytest.skip(f"Assembled grid not found: {DATA_DIR}")

        ff = load_dataset(
            region="land",
            start=MONTH_START,
            end=MONTH_END,
            features=DF_FEATURES,
            output_format="feature_frame",
            data_dir=DATA_DIR,
            gaul_dir=GAUL_DIR,
            month_id_epoch=MONTH_ID_EPOCH,
        )

        df = pd.DataFrame(
            ff.y_features,
            columns=ff.feature_names,
            index=pd.MultiIndex.from_arrays(
                [ff.identifiers["time"], ff.identifiers["unit"]],
                names=["month_id", "priogrid_gid"],
            ),
        )
        df = df.sort_index()

        mask = df.index.get_level_values("priogrid_gid").isin(
            reference_pgids,
        )
        df = df.loc[mask]
        result = build_parity_df(df)
        assert_consumer_parity(result, reference_df)


# ── Clone 3: Zarr consumer ──────────────────────────────


@pytest.mark.consumer
class TestZarrConsumer:
    """Load directly from zarr store via xarray."""

    def test_parity(
        self,
        reference_df: pd.DataFrame,
        reference_pgids: set[int],
    ) -> None:
        if not ZARR_PATH.exists():
            pytest.skip(f"Zarr store not found: {ZARR_PATH}")

        import xarray as xr

        from datafactory_adapters.grid_to_dataframe import (
            _compute_month_ids,
        )
        from datafactory_priogrid import from_views_month_id

        ds = xr.open_zarr(ZARR_PATH)

        # Temporal subsetting via datetime
        start_dt = from_views_month_id(MONTH_START).item()
        end_dt = from_views_month_id(MONTH_END).item()
        ds = ds.sel(time=slice(start_dt, end_dt))

        # Extract pgid grid and time axis
        pgid_2d = ds["pgid"].values  # [lat, lon]
        time_vals = ds["time"].values
        n_t = len(time_vals)
        n_h, n_w = pgid_2d.shape

        # Compute month_ids
        time_m = time_vals.astype("datetime64[M]")
        month_ids = _compute_month_ids(time_m, MONTH_ID_EPOCH)

        # Build flat index arrays
        pgids_flat = pgid_2d.ravel()
        all_pgids = np.tile(pgids_flat, n_t)
        all_month_ids = np.repeat(month_ids, n_h * n_w)

        # Stack feature data: [T*H*W, 3]
        data = np.stack(
            [
                ds[f].values.reshape(n_t * n_h * n_w)
                for f in DF_FEATURES
            ],
            axis=1,
        )

        # Filter to reference pgids
        ref_arr = np.array(sorted(reference_pgids))
        mask = np.isin(all_pgids, ref_arr)
        data = data[mask]
        all_pgids = all_pgids[mask]
        all_month_ids = all_month_ids[mask]

        df = pd.DataFrame(
            data,
            columns=DF_FEATURES,
            index=pd.MultiIndex.from_arrays(
                [all_month_ids, all_pgids],
                names=["month_id", "priogrid_gid"],
            ),
        )
        df = df.sort_index()

        result = build_parity_df(df)
        assert_consumer_parity(result, reference_df)
