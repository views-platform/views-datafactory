#!/usr/bin/env python3
"""Run the full V-Dem pipeline: harvest → viewpoint → compile.

Usage:
    uv run python scripts/run_vdem_pipeline.py
    uv run python scripts/run_vdem_pipeline.py --skip-to compile
    uv run python scripts/run_vdem_pipeline.py --end-year 2026

Consolidation is skipped — V-Dem is a single annual release with
nothing to merge (ADR-035, following ADR-029 precedent). The
viewpoint reads directly from the harvested Parquet.

No authentication required — V-Dem data is open access (CC-BY-SA).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

STEPS = ("harvest", "viewpoint", "compile")


def main() -> int:
    """Orchestrate the V-Dem pipeline end-to-end."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Run full V-Dem pipeline (Layers 1, 3, 4)",
    )
    parser.add_argument(
        "--skip-to",
        choices=("viewpoint", "compile"),
        default=None,
        help="Skip earlier steps (reuse existing data)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2026,
        help="Temporal range end year (default: 2026)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-download even if cached",
    )
    args = parser.parse_args()

    skip_idx = (
        STEPS.index(args.skip_to) if args.skip_to else 0
    )

    print("=" * 60)
    print("V-Dem PIPELINE (Layers 1, 3, 4)")
    print(f"End year: {args.end_year}")
    print("Consolidation: skipped (single release, ADR-035)")
    if args.skip_to:
        print(f"Skipping to: {args.skip_to}")
    print("=" * 60)
    print()

    t_start = time.monotonic()

    # ── Step 1: Harvest ──────────────────────────────────────

    raw_path = Path("data/raw/vdem/vdem_v16.parquet")

    if skip_idx < 1:
        print("[1/3] HARVEST")
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        config = VdemConfig()

        t0 = time.monotonic()
        try:
            result = fetch_vdem(
                config, force_refresh=args.force,
            )
        except Exception as e:
            print(f"  FAIL: {e}")
            return 1

        print(f"  Outcome: {result['outcome']}")
        if "n_rows" in result:
            print(f"  Rows: {result['n_rows']:,}")
        print(f"  ({time.monotonic() - t0:.1f}s)")
        print()
    else:
        if not raw_path.exists():
            print(
                f"FAIL: Expected {raw_path} but not found. "
                f"Run without --skip-to first."
            )
            return 1
        print(
            f"[1/3] HARVEST — skipped "
            f"(using {raw_path})"
        )
        print()

    # ── Step 2: Viewpoint ────────────────────────────────────

    viewpoint_path = Path("data/viewpoint/vdem_v1.parquet")

    if skip_idx < 2:
        print("[2/3] VIEWPOINT")
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        vp_config = VdemViewpointConfig(
            source_path=raw_path,
            output_path=viewpoint_path,
            ledger_path=Path(
                "provenance/viewpoint/"
                "vdem_v1_ledger.jsonl",
            ),
            end_year=args.end_year,
        )

        t0 = time.monotonic()
        try:
            result = build_vdem_v1(vp_config)
        except Exception as e:
            print(f"  FAIL: {e}")
            return 1

        print(
            f"  {result.n_events_output:,} rows → "
            f"{viewpoint_path}"
        )
        print(f"  ({time.monotonic() - t0:.1f}s)")
        print()
    else:
        if not viewpoint_path.exists():
            print(
                f"FAIL: Expected {viewpoint_path} "
                f"but not found."
            )
            return 1
        print(
            f"[2/3] VIEWPOINT — skipped "
            f"(using {viewpoint_path})"
        )
        print()

    # ── Step 3: Compile ──────────────────────────────────────

    print("[3/3] COMPILE")
    from datafactory_compilation import compile_pregridded
    from datafactory_compilation.pregridded_compilation import (
        PregriddedCompilationConfig,
    )
    from datafactory_priogrid import GridConfig, TemporalConfig
    from scripts.compile_vdem import VDEM_FEATURES

    output_dir = Path("data/compiled/vdem")

    config = PregriddedCompilationConfig(
        source_path=viewpoint_path,
        grid_config=GridConfig(),
        temporal_config=TemporalConfig(
            end_year=args.end_year,
        ),
        features=VDEM_FEATURES,
        output_dir=output_dir,
        ledger_path=Path(
            "provenance/compilation/vdem_ledger.jsonl",
        ),
    )

    t0 = time.monotonic()
    try:
        result_dir = compile_pregridded(config)
    except Exception as e:
        print(f"  FAIL: {e}")
        return 1

    import numpy as np

    grid = np.load(result_dir / "grid.npy", mmap_mode="r")
    print(f"  Grid shape: {grid.shape}")
    print(f"  Output: {result_dir}")
    print(f"  ({time.monotonic() - t0:.1f}s)")
    print()

    # ── Summary ──────────────────────────────────────────────

    total = time.monotonic() - t_start
    print("=" * 60)
    print(f"V-Dem PIPELINE COMPLETE ({total:.1f}s)")
    print(f"  Grid: {result_dir / 'grid.npy'}")
    print(f"  Shape: {grid.shape}")
    print()
    print(
        "Next: uv run python scripts/assemble_grid.py "
        "--vdem-grid data/compiled/vdem"
    )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
