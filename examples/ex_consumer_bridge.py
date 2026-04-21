#!/usr/bin/env python3
"""Verify: full consumer bridge pattern (load -> rename -> derive -> save).

This exercises the complete workflow a model's config_queryset.fetch_data()
performs: load from factory, rename columns, derive row/col from priogrid_gid,
fill NaN, save as parquet, and verify the parquet round-trips correctly.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
REGION = "africa_me_legacy"
START = 481
END = 483
NCOL = 720

FACTORY_FEATURES = ["ged_sb_best", "ged_ns_best", "ged_os_best", "gaul0_code"]
FEATURE_RENAME = {
    "ged_sb_best": "lr_sb_best",
    "ged_ns_best": "lr_ns_best",
    "ged_os_best": "lr_os_best",
    "gaul0_code": "c_id",
}


def main() -> int:
    df = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=FACTORY_FEATURES,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )

    df = df.rename(columns=FEATURE_RENAME)
    expected_cols = list(FEATURE_RENAME.values())
    assert list(df.columns) == expected_cols, (
        f"After rename: expected {expected_cols}, got {list(df.columns)}"
    )

    pgids = df.index.get_level_values("priogrid_gid")
    df["row"] = ((pgids - 1) // NCOL + 1).astype(np.float64)
    df["col"] = ((pgids - 1) % NCOL + 1).astype(np.float64)

    assert (df["row"] >= 1).all(), "Row values must be >= 1"
    assert (df["row"] <= 360).all(), "Row values must be <= 360"
    assert (df["col"] >= 1).all(), "Col values must be >= 1"
    assert (df["col"] <= 720).all(), "Col values must be <= 720"

    df = df.fillna(0.0)
    nan_count = df.isna().sum().sum()
    assert nan_count == 0, f"Found {nan_count} NaN after fillna"

    df = df.sort_index()

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test_viewser_df.parquet"
        df.to_parquet(out_path)

        assert out_path.exists(), "Parquet file not created"
        assert out_path.stat().st_size > 0, "Parquet file is empty"

        df_reloaded = pd.read_parquet(out_path)
        assert df_reloaded.shape == df.shape, (
            f"Round-trip shape mismatch: {df_reloaded.shape} vs {df.shape}"
        )
        assert list(df_reloaded.columns) == list(df.columns), (
            "Round-trip column mismatch"
        )

    print(f"PASS  ex_consumer_bridge — {len(df)} rows, "
          f"cols {list(df.columns)}, parquet round-trip OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_consumer_bridge — {e}")
        sys.exit(1)
