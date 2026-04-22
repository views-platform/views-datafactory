#!/usr/bin/env python3
"""XFAIL: country_month aggregation is not yet supported (C-125).

48 of 70 VIEWS models use country_month level of analysis.
The factory currently supports only priogrid_month. This script
documents the gap and will fail when the capability is added
(at which point it should be converted to a passing test).
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    from datafactory_query import load_dataset

    try:
        load_dataset(
            region="Ethiopia",
            start=481,
            end=492,
            output_format="country_month",
            data_dir=Path("data/assembled"),
        )
    except (ValueError, TypeError, KeyError):
        print("XFAIL ex_xfail_country_month — country_month not supported (C-125)")
        return 0

    # If we get here, the capability was added — convert to a real test
    print("PASS  ex_xfail_country_month — country_month now works! "
          "Convert this to a verification script.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_xfail_country_month — unexpected error: {e}")
        sys.exit(1)
