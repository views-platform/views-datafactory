#!/usr/bin/env python3
"""Verify: features parameter subsets columns correctly.

Tests that:
    - Requesting specific features returns only those columns
    - Requesting None returns all available features
    - Column order matches the request
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
REGION = "africa_me_legacy"
START = 481
END = 481

SUBSET = ["ged_os_best", "agri_gc", "mountains_mean"]


def main() -> int:
    df_subset = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=SUBSET,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )

    assert list(df_subset.columns) == SUBSET, (
        f"Expected columns {SUBSET}, got {list(df_subset.columns)}"
    )

    all_features = json.loads((DATA_DIR / "feature_names.json").read_text())

    df_all = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=None,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )

    assert list(df_all.columns) == all_features, (
        f"features=None: expected {len(all_features)} columns, "
        f"got {len(df_all.columns)}"
    )

    print(f"PASS  ex_feature_subset — subset={len(SUBSET)} cols, "
          f"all={len(all_features)} cols")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_feature_subset — {e}")
        sys.exit(1)
