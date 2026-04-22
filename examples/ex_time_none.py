#!/usr/bin/env python3
"""Verify: start=None, end=None returns the full dataset time range.

When no time bounds are given, load_dataset() should return all
available months in the assembled grid.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
REGION = "africa_me_legacy"
FEATURES = ["ged_sb_best"]


def main() -> int:
    time_steps = np.load(DATA_DIR / "time_steps.npy")
    n_months_in_grid = len(time_steps)

    df = load_dataset(
        region=REGION,
        start=None,
        end=None,
        features=FEATURES,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )

    actual_months = df.index.get_level_values("month_id").nunique()
    assert actual_months == n_months_in_grid, (
        f"Expected {n_months_in_grid} months (full grid), got {actual_months}"
    )

    print(f"PASS  ex_time_none — full range: {actual_months} months")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_time_none — {e}")
        sys.exit(1)
