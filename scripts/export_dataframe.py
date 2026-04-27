#!/usr/bin/env python3
"""Export compiled grid.npy to a DataFrame Parquet.

Usage:
    uv run python scripts/export_dataframe.py
    uv run python scripts/export_dataframe.py --input data/compiled
    uv run python scripts/export_dataframe.py --sparse
    uv run python scripts/export_dataframe.py --month-id-epoch 1980

Reads a compiled grid directory (grid.npy + pgids.npy +
time_steps.npy + feature_names.json) and produces a Parquet
DataFrame with (month_id, priogrid_gid) MultiIndex and one
column per feature.

By default, produces dense time series for all land cells
(64,818 cells x all months), with zeros where no events
occurred. The land mask is fetched from the PRIO-GRID API
and cached locally.

Use --sparse to include only non-zero rows instead.

This is a thin CLI wrapper around
datafactory_adapters.grid_to_dataframe().
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
        help="Non-zero rows only (default: dense land "
        "time series with zeros)",
    )
    parser.add_argument(
        "--month-id-epoch",
        type=int,
        default=0,
        help="Base year for month_id (0=raw, 1980=VIEWS)",
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

    mode = "sparse" if args.sparse else "dense (land)"
    print("=" * 60)
    print("DATAFRAME EXPORT")
    print(f"Input: {args.input}")
    print(f"Output: {output}")
    print(f"Mode: {mode}")
    print(f"month_id epoch: {args.month_id_epoch}")
    print("=" * 60)
    print()

    import numpy as np

    from datafactory_adapters import grid_to_dataframe
    from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG

    t0 = time.monotonic()

    grid = np.load(grid_path)
    pgids_2d = np.load(pgids_path)
    time_steps = np.load(time_path)
    feature_names = json.loads(features_path.read_text())

    DEFAULT_GRID_CONFIG.assert_grid_shape(grid)
    n_t, n_h, n_w, n_c = grid.shape
    print(f"Grid: [T={n_t}, H={n_h}, W={n_w}, C={n_c}]")
    print(f"Features: {feature_names}")

    # Get land mask for dense mode
    land_pgids = None
    if not args.sparse:
        from datafactory_priogrid.land_mask import (
            fetch_land_pgids,
        )

        land_pgids = fetch_land_pgids()
        print(f"Land cells: {len(land_pgids):,}")

    df = grid_to_dataframe(
        grid,
        pgids_2d,
        time_steps,
        feature_names,
        land_pgids=land_pgids,
        month_id_epoch=args.month_id_epoch,
        sparse=args.sparse,
    )

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
