#!/usr/bin/env python3
"""Verify: start/end as ISO strings in all accepted formats.

Accepted formats:
    - "2020"       (year-only: start=Jan, end=Dec)
    - "2020-01"    (year-month: exact month)
    - "2020-01-15" (full date: truncates to month)

Tests each format and verifies the output month range is correct.
"""

from __future__ import annotations

import sys
from pathlib import Path

from datafactory_query import load_dataset

DATA_DIR = Path("data/assembled")
REGION = "africa_me_legacy"
FEATURES = ["ged_sb_best"]


def month_id(year: int, month: int) -> int:
    return (year - 1980) * 12 + month


def get_months(start, end):
    df = load_dataset(
        region=REGION,
        start=start,
        end=end,
        features=FEATURES,
        output_format="dataframe",
        data_dir=DATA_DIR,
    )
    return set(df.index.get_level_values("month_id").unique())


def main() -> int:
    # Year-only: "2020" should give Jan-Dec 2020
    months_year = get_months("2020", "2020")
    expected_year = set(range(month_id(2020, 1), month_id(2020, 12) + 1))
    assert months_year == expected_year, (
        f"Year-only '2020': expected {len(expected_year)} months, "
        f"got {len(months_year)}"
    )

    # Year-month: "2020-06" to "2020-09" should give 4 months
    months_ym = get_months("2020-06", "2020-09")
    expected_ym = set(range(month_id(2020, 6), month_id(2020, 9) + 1))
    assert months_ym == expected_ym, (
        f"Year-month '2020-06' to '2020-09': expected {len(expected_ym)} months, "
        f"got {len(months_ym)}"
    )

    # Full date: "2020-03-15" should truncate to March 2020
    months_full = get_months("2020-03-15", "2020-03-15")
    expected_full = {month_id(2020, 3)}
    assert months_full == expected_full, (
        f"Full date '2020-03-15': expected month_id {month_id(2020, 3)}, "
        f"got {months_full}"
    )

    print("PASS  ex_time_iso_string — year-only (12mo), year-month (4mo), "
          "full-date truncation (1mo)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_time_iso_string — {e}")
        sys.exit(1)
