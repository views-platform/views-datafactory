#!/usr/bin/env python3
"""Run the full GHS-POP pipeline: harvest → viewpoint → compile.

Usage:
    uv run python scripts/run_ghspop_pipeline.py
    uv run python scripts/run_ghspop_pipeline.py --skip-to compile
    uv run python scripts/run_ghspop_pipeline.py --epochs 2020 2025
    uv run python scripts/run_ghspop_pipeline.py --end-year 2026

Consolidation is skipped — GHS-POP R2023A is a single release with
nothing to merge (ADR-029). The viewpoint reads directly from the
harvested GeoTIFF files.

No authentication required — JRC data is open access.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

STEPS = ("harvest", "viewpoint", "compile")


def main() -> int:
    """Orchestrate the GHS-POP pipeline end-to-end."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Run full GHS-POP pipeline (Layers 1, 3, 4)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        nargs="+",
        default=None,
        help=(
            "GHS-POP epochs to process "
            "(default: all 12 epochs 1975–2030)"
        ),
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

    epoch_label = (
        str(args.epochs) if args.epochs
        else "all (1975–2030)"
    )

    print("=" * 60)
    print("GHS-POP PIPELINE (Layers 1, 3, 4)")
    print(f"Epochs: {epoch_label}")
    print(f"End year: {args.end_year}")
    print("Consolidation: skipped (single release, ADR-029)")
    if args.skip_to:
        print(f"Skipping to: {args.skip_to}")
    print("=" * 60)
    print()

    t_start = time.monotonic()

    # ── Step 1: Harvest ──────────────────────────────────────

    raw_dir = Path("data/raw/ghspop")

    if skip_idx < 1:
        print("[1/3] HARVEST")
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        harvest_kwargs: dict = {}
        if args.epochs is not None:
            harvest_kwargs["epochs"] = tuple(args.epochs)

        config = GhsPopConfig(
            data_dir=raw_dir,
            ledger_path=Path(
                "provenance/ghspop/ingestion_ledger.jsonl",
            ),
            **harvest_kwargs,
        )

        t0 = time.monotonic()
        try:
            results = fetch_ghspop(
                config, force_refresh=args.force,
            )
        except Exception as e:
            print(f"  FAIL: {e}")
            return 1

        n_cached = sum(
            1 for r in results if r["outcome"] == "cached"
        )
        n_new = sum(
            1 for r in results if r["outcome"] == "success"
        )
        print(
            f"  {len(results)} epochs: "
            f"{n_new} downloaded, {n_cached} cached → {raw_dir}"
        )
        print(f"  ({time.monotonic() - t0:.1f}s)")
        print()
    else:
        tif_files = sorted(raw_dir.glob("*.tif"))
        if not tif_files:
            print(
                f"FAIL: No GeoTIFF files in {raw_dir}. "
                f"Run without --skip-to first."
            )
            return 1
        print(
            f"[1/3] HARVEST — skipped "
            f"({len(tif_files)} GeoTIFFs in {raw_dir})"
        )
        print()

    # ── Step 2: Viewpoint ────────────────────────────────────

    viewpoint_path = Path("data/viewpoint/ghspop_v1.parquet")

    if skip_idx < 2:
        print("[2/3] VIEWPOINT")
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        vp_kwargs: dict = {}
        if args.epochs is not None:
            vp_kwargs["epochs"] = tuple(args.epochs)

        vp_config = GhsPopViewpointConfig(
            source_dir=raw_dir,
            output_path=viewpoint_path,
            ledger_path=Path(
                "provenance/viewpoint/"
                "ghspop_v1_ledger.jsonl",
            ),
            **vp_kwargs,
        )

        t0 = time.monotonic()
        try:
            result = build_ghspop_v1(vp_config)
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
        PregriddedFeatureSpec,
    )
    from datafactory_priogrid import GridConfig, TemporalConfig

    output_dir = Path("data/compiled/ghspop")

    config = PregriddedCompilationConfig(
        source_path=viewpoint_path,
        grid_config=GridConfig(),
        temporal_config=TemporalConfig(
            end_year=args.end_year,
        ),
        features=(
            PregriddedFeatureSpec(
                "ghspop_pop_count", "pop_count",
            ),
        ),
        output_dir=output_dir,
        ledger_path=Path(
            "provenance/compilation/ghspop_ledger.jsonl",
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
    print(f"GHS-POP PIPELINE COMPLETE ({total:.1f}s)")
    print(f"  Grid: {result_dir / 'grid.npy'}")
    print(f"  Shape: {grid.shape}")
    print()
    print(
        "Next: uv run python scripts/assemble_grid.py "
        "--ghspop-grid data/compiled/ghspop"
    )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
