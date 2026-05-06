#!/usr/bin/env python3
"""Layer 4: Compile ACLED event data onto the PRIO-GRID.

Usage:
    uv run python scripts/compile_acled.py
    uv run python scripts/compile_acled.py --source data/viewpoint/acled_v1.parquet
    uv run python scripts/compile_acled.py --start-year 1997 --end-year 2025

Reads an ACLED viewpoint Parquet and produces npy arrays on the
259,200-cell PRIO-GRID with 8 feature columns (ADR-028):
  acled_count, acled_battles, acled_explosions, acled_vac,
  acled_protests, acled_riots, acled_strategic, acled_fatalities

Does NOT fetch data, consolidate, or build viewpoints.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    """Compile ACLED events to PRIO-GRID."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Compile ACLED to PRIO-GRID (Layer 4)"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/viewpoint/acled_v1.parquet"),
        help="Source Parquet file (ACLED viewpoint output)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/compiled/acled"),
        help="Output directory for grid.npy + sidecars",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=1997,
        help="Temporal range start year (default: 1997)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2025,
        help="Temporal range end year (default: 2025)",
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=Path("provenance"),
        help="Provenance directory",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ACLED PRIO-GRID COMPILER (Layer 4)")
    print(f"Source: {args.source}")
    print(f"Output: {args.output_dir}")
    print(
        f"Temporal: {args.start_year}-01 to "
        f"{args.end_year}-12"
    )
    print("=" * 60)
    print()

    if not args.source.exists():
        print(f"FAIL: Source not found: {args.source}")
        print(
            "Run the ACLED viewpoint builder first."
        )
        return 1

    from datafactory_compilation import compile_grid
    from datafactory_compilation.compilation_config import (
        CompilationConfig,
        FeatureSpec,
    )
    from datafactory_priogrid import GridConfig, TemporalConfig

    config = CompilationConfig(
        source_path=args.source,
        grid_config=GridConfig(),
        temporal_config=TemporalConfig(
            start_year=args.start_year,
            end_year=args.end_year,
        ),
        features=(
            FeatureSpec("acled_count", "count"),
            FeatureSpec(
                "acled_battles", "count",
                {"event_type": "Battles"},
            ),
            FeatureSpec(
                "acled_explosions", "count",
                {"event_type": "Explosions/Remote violence"},
            ),
            FeatureSpec(
                "acled_vac", "count",
                {"event_type": "Violence against civilians"},
            ),
            FeatureSpec(
                "acled_protests", "count",
                {"event_type": "Protests"},
            ),
            FeatureSpec(
                "acled_riots", "count",
                {"event_type": "Riots"},
            ),
            FeatureSpec(
                "acled_strategic", "count",
                {"event_type": "Strategic developments"},
            ),
            FeatureSpec(
                "acled_fatalities", "sum_field",
                value_field="fatalities",
            ),
        ),
        output_dir=args.output_dir,
        ledger_path=(
            args.provenance_dir
            / "compilation"
            / "acled_ledger.jsonl"
        ),
        date_field="event_date",
        lat_field="latitude",
        lon_field="longitude",
    )

    n_cells = config.grid_config.n_cells
    n_months = config.temporal_config.n_steps
    print(f"Grid: {n_cells:,} cells x {n_months} months")
    print(f"Features: {len(config.features)}")
    print()

    t0 = time.monotonic()
    try:
        import numpy as np

        output_dir = compile_grid(config)
        elapsed = time.monotonic() - t0

        from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG

        grid = np.load(output_dir / "grid.npy")
        DEFAULT_GRID_CONFIG.assert_grid_shape(grid)

        print(f"Grid shape: {grid.shape}")
        print(f"  [T={grid.shape[0]}, "
              f"H={grid.shape[1]}, "
              f"W={grid.shape[2]}, "
              f"C={grid.shape[3]}]")
        print(
            f"Non-zero bins: "
            f"{(grid[:, :, :, 0] > 0).sum():,}"
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
