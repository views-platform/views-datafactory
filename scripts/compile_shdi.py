#!/usr/bin/env python3
"""Compile SHDI viewpoint output onto the spatiotemporal grid.

Usage:
    uv run python scripts/compile_shdi.py
    uv run python scripts/compile_shdi.py --source data/viewpoint/shdi_v1.parquet
    uv run python scripts/compile_shdi.py --end-year 2024

Uses pregridded_compilation — SHDI viewpoint output is already
keyed by (pgid, month_id). No lat/lon lookup needed.

SHDI is an intensive quantity (ADR-040): fill_value is NaN.

Ref: ADR-036 (SHDI source selection).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from datafactory_compilation import compile_pregridded
from datafactory_compilation.pregridded_compilation import (
    PregriddedCompilationConfig,
    PregriddedFeatureSpec,
)
from datafactory_priogrid import GridConfig, TemporalConfig

SHDI_FEATURES: tuple[PregriddedFeatureSpec, ...] = (
    PregriddedFeatureSpec("shdi_shdi", "shdi"),
    PregriddedFeatureSpec("shdi_healthindex", "healthindex"),
    PregriddedFeatureSpec("shdi_edindex", "edindex"),
    PregriddedFeatureSpec("shdi_incindex", "incindex"),
)


def main() -> int:
    """Compile SHDI viewpoint output onto the grid."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Compile SHDI viewpoint output to grid",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/viewpoint/shdi_v1.parquet"),
        help="Viewpoint Parquet path",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/compiled/shdi"),
        help="Output directory for grid.npy",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2026,
        help="Temporal range end year (default: 2026)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("SHDI COMPILATION")
    print(f"Source: {args.source}")
    print(f"Output: {args.output_dir}")
    print(f"Features: {len(SHDI_FEATURES)}")
    print("=" * 60)
    print()

    config = PregriddedCompilationConfig(
        source_path=args.source,
        grid_config=GridConfig(),
        temporal_config=TemporalConfig(
            end_year=args.end_year,
        ),
        features=SHDI_FEATURES,
        output_dir=args.output_dir,
        ledger_path=Path(
            "provenance/compilation/shdi_ledger.jsonl",
        ),
        fill_value=float("nan"),
    )

    t0 = time.monotonic()
    try:
        result_dir = compile_pregridded(config)
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    grid = np.load(result_dir / "grid.npy", mmap_mode="r")
    elapsed = time.monotonic() - t0

    print(f"Grid shape: {grid.shape}")
    print(f"Output: {result_dir}")
    print(f"({elapsed:.1f}s)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
