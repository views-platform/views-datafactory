#!/usr/bin/env python3
"""Verify: load_dataset(output_format='dataframe') returns correct contract.

Expected output:
    - pandas DataFrame
    - MultiIndex with levels (month_id, priogrid_gid)
    - Columns are the requested features
    - Values are float32 (from grid)
    - Index is sorted
    - No NaN in output
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
REGION = "africa_me_legacy"
START = 481  # Jan 2020
END = 492    # Dec 2020
FEATURES = ["ged_sb_best", "ged_ns_best", "ged_os_best"]


def main() -> int:
    df = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=FEATURES,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )

    assert isinstance(df, pd.DataFrame), f"Expected DataFrame, got {type(df)}"

    assert df.index.names == ["month_id", "priogrid_gid"], (
        f"Expected MultiIndex (month_id, priogrid_gid), got {df.index.names}"
    )

    assert list(df.columns) == FEATURES, (
        f"Expected columns {FEATURES}, got {list(df.columns)}"
    )

    assert len(df) > 0, "DataFrame is empty"

    month_ids = df.index.get_level_values("month_id")
    assert month_ids.min() >= START, (
        f"Month range starts at {month_ids.min()}, expected >= {START}"
    )
    assert month_ids.max() <= END, (
        f"Month range ends at {month_ids.max()}, expected <= {END}"
    )

    assert df.index.is_monotonic_increasing, "Index is not sorted"

    nan_count = df.isna().sum().sum()
    assert nan_count == 0, f"Found {nan_count} NaN values"

    for col in FEATURES:
        assert df[col].dtype.name.startswith("float"), (
            f"Column {col} has dtype {df[col].dtype}, expected float"
        )

    print(f"PASS  ex_dataframe_output — {len(df)} rows, {len(df.columns)} cols, "
          f"months {month_ids.min()}-{month_ids.max()}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_dataframe_output — {e}")
        sys.exit(1)
