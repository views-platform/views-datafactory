#!/usr/bin/env python3
"""Layer 4: Compile event data onto the PRIO-GRID.

Usage:
    uv run python scripts/compile_grid.py
    uv run python scripts/compile_grid.py --source data/viewpoints/parity.parquet
    uv run python scripts/compile_grid.py --end-year 2026

Reads a viewpoint Parquet (or any event Parquet with lat, lon, date
columns) and produces npy arrays on the 259,200-cell PRIO-GRID.

Does NOT fetch data, consolidate, or build viewpoints.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    """Compile events to PRIO-GRID."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Compile to PRIO-GRID (Layer 4)"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(
            "data/viewpoint/production_parity.parquet"
        ),
        help="Source Parquet file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/compiled"),
        help="Output directory for grid.npy + sidecars",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=1989,
        help="Temporal range start year (default: 1989)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2026,
        help="Temporal range end year (default: 2026)",
    )
    parser.add_argument(
        "--date-field",
        default="date_month",
        help=(
            "Date column for temporal binning "
            "(default: date_month for viewpoint output, "
            "use date_start for raw data)"
        ),
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=Path("provenance"),
        help="Provenance directory",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PRIO-GRID COMPILER (Layer 4)")
    print(f"Source: {args.source}")
    print(f"Output: {args.output_dir}")
    print(
        f"Temporal: {args.start_year}-01 to "
        f"{args.end_year}-12"
    )
    print(f"Date field: {args.date_field}")
    print("=" * 60)
    print()

    if not args.source.exists():
        print(f"FAIL: Source not found: {args.source}")
        print(
            "Run scripts/build_viewpoint.py first."
        )
        return 1

    from datafactory_compilation import compile_grid
    from datafactory_compilation.compilation_config import (
        CompilationConfig,
        FeatureSpec,
    )
    from datafactory_priogrid import GridConfig, TemporalConfig

    # Disaggregated by UCDP type of violence:
    #   1 = state-based (sb), 2 = non-state (ns), 3 = one-sided (os)
    config = CompilationConfig(
        source_path=args.source,
        grid_config=GridConfig(),
        temporal_config=TemporalConfig(
            start_year=args.start_year,
            end_year=args.end_year,
        ),
        features=(
            FeatureSpec(
                "ged_sb_count", "count",
                {"type_of_violence": 1},
            ),
            FeatureSpec(
                "ged_sb_best", "sum_best",
                {"type_of_violence": 1},
            ),
            FeatureSpec(
                "ged_ns_count", "count",
                {"type_of_violence": 2},
            ),
            FeatureSpec(
                "ged_ns_best", "sum_best",
                {"type_of_violence": 2},
            ),
            FeatureSpec(
                "ged_os_count", "count",
                {"type_of_violence": 3},
            ),
            FeatureSpec(
                "ged_os_best", "sum_best",
                {"type_of_violence": 3},
            ),
        ),
        output_dir=args.output_dir,
        ledger_path=(
            args.provenance_dir
            / "compilation"
            / "ledger.jsonl"
        ),
        date_field=args.date_field,
    )

    n_cells = config.grid_config.n_cells
    n_months = config.temporal_config.n_steps
    print(f"Grid: {n_cells:,} cells x {n_months} months")
    print()

    t0 = time.monotonic()
    try:
        import numpy as np

        output_dir = compile_grid(config)
        elapsed = time.monotonic() - t0

        grid = np.load(output_dir / "grid.npy")
        # [T, H, W, C] — sum first feature across all dims
        first_feat = grid[:, :, :, 0]

        print(f"Grid shape: {grid.shape}")
        print(f"  [T={grid.shape[0]}, "
              f"H={grid.shape[1]}, "
              f"W={grid.shape[2]}, "
              f"C={grid.shape[3]}]")
        print(
            f"Non-zero bins: "
            f"{(first_feat > 0).sum():,}"
        )
        print(
            f"Total across all features: "
            f"{grid.sum():,.0f}"
        )
        print(f"Output: {output_dir}")
        print(f"Time: {elapsed:.1f}s")
        print("PASS")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
