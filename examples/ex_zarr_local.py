#!/usr/bin/env python3
"""Verify: local zarr store as data backend.

Tests that data_dir pointing to a local .zarr directory loads
correctly: correct output type, index structure, and column names.

Note: values are NOT compared against npy because the zarr store
and npy grid may have been assembled at different times. Structure
parity is sufficient here; value parity is tested separately by
the consumer parity tests (test_consumer_parity.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from datafactory_query import load_dataset

DATA_DIR_ZARR = Path("data/assembled/grid.zarr")
REGION = "africa_me_legacy"
START = 481
END = 483
FEATURES = ["ged_sb_best", "ged_ns_best"]


def main() -> int:
    if not DATA_DIR_ZARR.exists():
        print("SKIP  ex_zarr_local — grid.zarr not found at data/assembled/grid.zarr")
        return 0

    df_zarr = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=FEATURES,
        output_format="dataframe",
        data_dir=str(DATA_DIR_ZARR),
    )

    assert isinstance(df_zarr, pd.DataFrame), f"Expected DataFrame, got {type(df_zarr)}"
    assert len(df_zarr) > 0, "DataFrame is empty"

    assert df_zarr.index.names == ["month_id", "priogrid_gid"], (
        f"Expected MultiIndex (month_id, priogrid_gid), got {df_zarr.index.names}"
    )

    assert set(df_zarr.columns) == set(FEATURES), (
        f"Expected features {FEATURES}, got {list(df_zarr.columns)}"
    )

    month_ids = df_zarr.index.get_level_values("month_id")
    assert month_ids.min() >= START, (
        f"Month range starts at {month_ids.min()}, expected >= {START}"
    )
    assert month_ids.max() <= END, (
        f"Month range ends at {month_ids.max()}, expected <= {END}"
    )

    pgids = df_zarr.index.get_level_values("priogrid_gid")
    assert pgids.nunique() > 0, "No grid cells in output"

    print(f"PASS  ex_zarr_local — {len(df_zarr)} rows, "
          f"{pgids.nunique()} cells, months {month_ids.min()}-{month_ids.max()}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_zarr_local — {e}")
        sys.exit(1)
