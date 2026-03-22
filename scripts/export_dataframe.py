#!/usr/bin/env python3
"""Export compiled grid.npy to a DataFrame Parquet.

Usage:
    uv run python scripts/export_dataframe.py
    uv run python scripts/export_dataframe.py --input data/compiled
    uv run python scripts/export_dataframe.py --sparse

Reads a compiled grid directory (grid.npy + pgids.npy +
time_steps.npy + feature_names.json) and produces a Parquet
DataFrame with (month_id, priogrid_gid) MultiIndex and one
column per feature.

By default, produces full time series for all land cells
(64,818 cells x all months), with zeros where no events
occurred. The land mask is fetched from the PRIO-GRID API
and cached locally.

Use --sparse to include only non-zero rows instead.

This is a consumer-side adapter, not part of the compiler.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    """Export grid to DataFrame."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Export compiled grid to DataFrame"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/compiled"),
        help="Compiled grid directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output Parquet path",
    )
    parser.add_argument(
        "--sparse",
        action="store_true",
        help="Non-zero rows only (default: full land "
        "time series with zeros)",
    )
    args = parser.parse_args()

    grid_path = args.input / "grid.npy"
    pgids_path = args.input / "pgids.npy"
    time_path = args.input / "time_steps.npy"
    features_path = args.input / "feature_names.json"
    output = args.output or (
        args.input / "dataframe.parquet"
    )

    for p in [grid_path, pgids_path, time_path, features_path]:
        if not p.exists():
            print(f"FAIL: {p} not found")
            return 1

    mode = "sparse" if args.sparse else "land (full time series)"
    print("=" * 60)
    print("DATAFRAME EXPORT")
    print(f"Input: {args.input}")
    print(f"Output: {output}")
    print(f"Mode: {mode}")
    print("=" * 60)
    print()

    import numpy as np
    import pandas as pd

    t0 = time.monotonic()

    # Load compiled data
    grid = np.load(grid_path)  # [T, H, W, C]
    pgids_2d = np.load(pgids_path)  # [H, W]
    time_steps = np.load(time_path)  # [T]
    feature_names = json.loads(features_path.read_text())

    n_t, n_h, n_w, n_c = grid.shape
    print(f"Grid: [T={n_t}, H={n_h}, W={n_w}, C={n_c}]")
    print(f"Features: {feature_names}")

    # Build month_id from time_steps (datetime64[M])
    dates = time_steps.astype("datetime64[M]")
    years = dates.astype("datetime64[Y]").astype(int) + 1970
    months = (
        dates.astype(int)
        - dates.astype("datetime64[Y]").astype(int)
    ) + 1
    month_ids = years * 12 + months

    # Flatten grid to (T*H*W, C)
    flat_grid = grid.reshape(n_t * n_h * n_w, n_c)

    # Build index arrays
    pgids_flat = pgids_2d.ravel()  # [H*W]
    all_pgids = np.tile(pgids_flat, n_t)
    all_month_ids = np.repeat(month_ids, n_h * n_w)

    if args.sparse:
        # Keep only rows with at least one non-zero feature
        mask = flat_grid.any(axis=1)
        flat_grid = flat_grid[mask]
        all_pgids = all_pgids[mask]
        all_month_ids = all_month_ids[mask]
        print(
            f"Sparse: {mask.sum():,} non-zero rows "
            f"of {len(mask):,} total"
        )
    else:
        # Full time series for all land cells
        from datafactory_priogrid.land_mask import (
            fetch_land_pgids,
        )

        land_pgids = fetch_land_pgids()
        land_mask = np.isin(all_pgids, list(land_pgids))
        n_total = len(all_pgids)
        flat_grid = flat_grid[land_mask]
        all_pgids = all_pgids[land_mask]
        all_month_ids = all_month_ids[land_mask]
        n_land = len(all_pgids)
        print(
            f"Land cells: {len(land_pgids):,} "
            f"x {n_t} months = {n_land:,} rows "
            f"(dropped {n_total - n_land:,} ocean)"
        )

    # Build DataFrame
    index = pd.MultiIndex.from_arrays(
        [all_month_ids, all_pgids],
        names=["month_id", "priogrid_gid"],
    )
    df = pd.DataFrame(
        flat_grid,
        index=index,
        columns=feature_names,
    )
    df = df.sort_index()

    # Write
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output)

    elapsed = time.monotonic() - t0
    print(f"Rows: {len(df):,}")
    print(f"Columns: {list(df.columns)}")
    print(f"Index: {df.index.names}")
    print(f"Output: {output}")
    print(f"Time: {elapsed:.1f}s")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
