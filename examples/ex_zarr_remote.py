#!/usr/bin/env python3
"""Verify: remote zarr store over HTTP.

Tests that data_dir="http://...grid.zarr" loads correctly over
the network. Requires ~/.netrc credentials for the server.

This script is skipped by run_examples.sh unless --include-remote
is passed, since it requires network access and server availability.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from datafactory_query import load_dataset
from datafactory_query.defaults import DEFAULT_REMOTE

ZARR_URL = DEFAULT_REMOTE.zarr_url
REGION = "africa_me_legacy"
START = 481
END = 481  # single month to minimize download
FEATURES = ["ged_sb_best"]


def main() -> int:
    netrc = Path.home() / ".netrc"
    if not netrc.exists():
        print("SKIP  ex_zarr_remote — ~/.netrc not found")
        return 0

    df = load_dataset(
        region=REGION,
        start=START,
        end=END,
        features=FEATURES,
        output_format="dataframe",
        data_dir=ZARR_URL,
    )

    assert isinstance(df, pd.DataFrame), f"Expected DataFrame, got {type(df)}"
    assert len(df) > 0, "DataFrame is empty"

    assert df.index.names == ["month_id", "priogrid_gid"], (
        f"Expected MultiIndex (month_id, priogrid_gid), got {df.index.names}"
    )

    pgids = df.index.get_level_values("priogrid_gid")
    assert pgids.nunique() > 1000, (
        f"Expected >1000 cells for africa_me_legacy, got {pgids.nunique()}"
    )

    assert list(df.columns) == FEATURES or set(df.columns) == set(FEATURES), (
        f"Expected features {FEATURES}, got {list(df.columns)}"
    )

    print(f"PASS  ex_zarr_remote — {len(df)} rows, {pgids.nunique()} cells "
          f"from {ZARR_URL}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_zarr_remote — {e}")
        sys.exit(1)
