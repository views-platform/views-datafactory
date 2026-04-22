#!/usr/bin/env python3
"""Verify: local npy directory as data backend.

Tests that data_dir=Path(...) loads from the npy assembled grid
and produces consistent output between DataFrame and FeatureFrame formats.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
REGION = "africa_me_legacy"
START = 481
END = 483
FEATURES = ["ged_sb_best", "ged_ns_best"]


def main() -> int:
    assert DATA_DIR.is_dir(), f"Data directory not found: {DATA_DIR}"
    assert (DATA_DIR / "grid.npy").exists(), "grid.npy not found"
    assert (DATA_DIR / "pgids.npy").exists(), "pgids.npy not found"
    assert (DATA_DIR / "time_steps.npy").exists(), "time_steps.npy not found"

    df = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=FEATURES,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )

    ff = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=FEATURES,
        output_format="feature_frame",
        data_dir=DATA_DIR,
    )

    assert len(df) == ff.y_features.shape[0], (
        f"Row count mismatch: DataFrame={len(df)}, "
        f"FeatureFrame={ff.y_features.shape[0]}"
    )

    assert len(df.columns) == ff.y_features.shape[1], (
        f"Feature count mismatch: DataFrame={len(df.columns)}, "
        f"FeatureFrame={ff.y_features.shape[1]}"
    )

    df_values = df.values.astype(np.float32)
    ff_values = ff.y_features.astype(np.float32)
    assert np.allclose(df_values, ff_values, equal_nan=True), (
        "Value mismatch between DataFrame and FeatureFrame outputs"
    )

    print(f"PASS  ex_npy_backend — npy path, {len(df)} rows, "
          f"DataFrame/FeatureFrame consistent")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_npy_backend — {e}")
        sys.exit(1)
