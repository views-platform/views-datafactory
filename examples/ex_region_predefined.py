#!/usr/bin/env python3
"""Verify: predefined macro-regions return expected cell counts.

Tests that each predefined region name resolves to the correct
number of PRIO-GRID cells per time step.
"""

from __future__ import annotations

import sys
from pathlib import Path

from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
START = 481
END = 481  # single month to keep fast
FEATURES = ["ged_sb_best"]

EXPECTED_CELLS = {
    "global": 259200,
    "land": 64818,
    "africa_me_legacy": 13110,
}


def main() -> int:
    for region, expected in EXPECTED_CELLS.items():
        df = load_dataset(
            region=region,
            start=START,
            end=END,
            features=FEATURES,
            output_format="dataframe",
            data_dir=DATA_DIR,
        )

        unique_pgids = df.index.get_level_values("priogrid_gid").nunique()
        assert unique_pgids == expected, (
            f"Region '{region}': expected {expected} cells, got {unique_pgids}"
        )

    detail = ", ".join(f"{r}={c}" for r, c in EXPECTED_CELLS.items())
    print(f"PASS  ex_region_predefined — {detail}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_region_predefined — {e}")
        sys.exit(1)
