#!/usr/bin/env python3
"""Verify: start/end as VIEWS month_id integers.

VIEWS encoding: month_id = (year - 1980) * 12 + month.
Tests that the output DataFrame contains exactly the requested months.
"""

from __future__ import annotations

import sys
from pathlib import Path

from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
REGION = "africa_me_legacy"
FEATURES = ["ged_sb_best"]

# Jan 2020 = (2020-1980)*12 + 1 = 481
# Dec 2020 = (2020-1980)*12 + 12 = 492
START = 481
END = 492
EXPECTED_MONTHS = set(range(481, 493))


def main() -> int:
    df = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=FEATURES,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )

    actual_months = set(df.index.get_level_values("month_id").unique())
    assert actual_months == EXPECTED_MONTHS, (
        f"Expected months {min(EXPECTED_MONTHS)}-{max(EXPECTED_MONTHS)}, "
        f"got {min(actual_months)}-{max(actual_months)} "
        f"(missing: {EXPECTED_MONTHS - actual_months}, "
        f"extra: {actual_months - EXPECTED_MONTHS})"
    )

    print(f"PASS  ex_time_month_id — months {START}-{END}, "
          f"{len(actual_months)} unique months")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_time_month_id — {e}")
        sys.exit(1)
