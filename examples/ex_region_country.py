#!/usr/bin/env python3
"""Verify: country-name region lookup via FAO GAUL.

Tests that:
    - A known country name returns a non-empty subset
    - Case-insensitive lookup works (e.g. "ethiopia" == "Ethiopia")
    - An unknown country name raises an error
"""

from __future__ import annotations

import sys
from pathlib import Path

from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
START = 481
END = 481
FEATURES = ["ged_sb_best"]


def main() -> int:
    df_proper = load_dataset(
        region="Ethiopia",
        start=START,
        end=END,
        features=FEATURES,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )

    n_cells = df_proper.index.get_level_values("priogrid_gid").nunique()
    assert n_cells > 0, "Ethiopia returned 0 cells"

    df_lower = load_dataset(
        region="ethiopia",
        start=START,
        end=END,
        features=FEATURES,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )

    n_cells_lower = df_lower.index.get_level_values("priogrid_gid").nunique()
    assert n_cells == n_cells_lower, (
        f"Case mismatch: 'Ethiopia'={n_cells} cells, 'ethiopia'={n_cells_lower} cells"
    )

    try:
        load_dataset(
            region="NotARealCountry",
            start=START,
            end=END,
            features=FEATURES,
            output_format="dataframe",
            data_dir=DATA_DIR,
        )
        raise AssertionError("Expected error for unknown country, but call succeeded")
    except (ValueError, KeyError):
        pass  # expected

    print(f"PASS  ex_region_country — Ethiopia={n_cells} cells, "
          f"case-insensitive OK, unknown raises OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_region_country — {e}")
        sys.exit(1)
