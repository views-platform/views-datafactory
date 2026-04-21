#!/usr/bin/env python3
"""Verify: load_dataset(output_format='feature_frame') returns correct contract.

Expected output:
    - FeatureFrame instance
    - y_features shape (N, D) with dtype float32
    - identifiers dict with "time" and "unit" arrays of length N
    - feature_names list of length D
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from datafactory_adapters import FeatureFrame
from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
REGION = "africa_me_legacy"
START = 481
END = 492
FEATURES = ["ged_sb_best", "ged_ns_best", "ged_os_best"]


def main() -> int:
    ff = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=FEATURES,
        output_format="feature_frame",
        data_dir=DATA_DIR,
    )

    assert isinstance(ff, FeatureFrame), f"Expected FeatureFrame, got {type(ff)}"

    assert ff.y_features.ndim == 2, f"Expected 2D array, got {ff.y_features.ndim}D"

    n_rows, n_features = ff.y_features.shape
    assert n_rows > 0, "FeatureFrame is empty"
    assert n_features == len(FEATURES), (
        f"Expected {len(FEATURES)} features, got {n_features}"
    )

    assert ff.y_features.dtype == np.float32, (
        f"Expected float32, got {ff.y_features.dtype}"
    )

    assert ff.feature_names == FEATURES, (
        f"Expected feature_names {FEATURES}, got {ff.feature_names}"
    )

    assert "time" in ff.identifiers, "Missing 'time' in identifiers"
    assert "unit" in ff.identifiers, "Missing 'unit' in identifiers"
    assert len(ff.identifiers["time"]) == n_rows, (
        f"time array length {len(ff.identifiers['time'])} != {n_rows} rows"
    )
    assert len(ff.identifiers["unit"]) == n_rows, (
        f"unit array length {len(ff.identifiers['unit'])} != {n_rows} rows"
    )

    nan_count = int(np.isnan(ff.y_features).sum())
    assert nan_count == 0, f"Found {nan_count} NaN values in y_features"

    print(f"PASS  ex_feature_frame_output — shape {ff.y_features.shape}, "
          f"features {ff.feature_names}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_feature_frame_output — {e}")
        sys.exit(1)
