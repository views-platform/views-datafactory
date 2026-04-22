#!/usr/bin/env python3
"""XFAIL: no feature transform layer exists (C-126).

67+ VIEWS models use viewser transforms (tlag, spatial.lag, decay, ln,
etc.). The factory provides raw values only — feature engineering is
out of scope and will live in a separate repo or model classes.

This script documents the gap. It checks whether datafactory_query
has gained a transforms module; if not, reports XFAIL.
"""

from __future__ import annotations

import sys


def main() -> int:
    import datafactory_query

    if hasattr(datafactory_query, "transforms"):
        print("PASS  ex_xfail_transforms — transforms module now exists! "
              "Convert this to a verification script.")
        return 0

    print("XFAIL ex_xfail_transforms — no transforms module (C-126)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_xfail_transforms — unexpected error: {e}")
        sys.exit(1)
