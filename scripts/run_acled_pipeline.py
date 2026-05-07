#!/usr/bin/env python3
"""Run the full ACLED pipeline: harvest → consolidate → viewpoint → compile.

Usage:
    uv run python scripts/run_acled_pipeline.py
    uv run python scripts/run_acled_pipeline.py --start-year 2020 --end-year 2025
    uv run python scripts/run_acled_pipeline.py --skip-to compile

Requires ACLED_USERNAME and ACLED_PASSWORD environment variables.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

STEPS = ("harvest", "consolidate", "viewpoint", "compile")


def main() -> int:
    """Orchestrate the ACLED pipeline end-to-end."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Run full ACLED pipeline (Layers 1–4)",
    )
    parser.add_argument(
        "--start-year", type=int, default=2020,
        help="Harvest start year (default: 2020)",
    )
    parser.add_argument(
        "--end-year", type=int, default=2025,
        help="Harvest end year (default: 2025)",
    )
    parser.add_argument(
        "--skip-to",
        choices=("consolidate", "viewpoint", "compile"),
        default=None,
        help="Skip earlier steps (reuse existing data)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-fetch even if data exists",
    )
    args = parser.parse_args()

    skip_idx = (
        STEPS.index(args.skip_to) if args.skip_to else 0
    )

    print("=" * 60)
    print("ACLED PIPELINE (Layers 1–4)")
    print(f"Range: {args.start_year}–{args.end_year}")
    if args.skip_to:
        print(f"Skipping to: {args.skip_to}")
    print("=" * 60)
    print()

    t_start = time.monotonic()

    # ── Step 1: Harvest ──────────────────────────────────────

    raw_dir = Path("data/raw/acled")

    if skip_idx < 1:
        if (
            not os.environ.get("ACLED_USERNAME")
            or not os.environ.get("ACLED_PASSWORD")
        ):
            print(
                "FAIL: Set ACLED_USERNAME and ACLED_PASSWORD "
                "environment variables."
            )
            return 1

        print("[1/4] HARVEST")
        from datafactory_harvester.sources.acled import (
            AcledConfig,
            fetch_acled,
        )

        config = AcledConfig(
            start_year=args.start_year,
            end_year=args.end_year,
            data_dir=raw_dir,
            ledger_path=Path(
                "provenance/acled/ingestion_ledger.jsonl",
            ),
        )

        t0 = time.monotonic()
        try:
            data_dir = fetch_acled(
                config, force_refresh=args.force,
            )
        except Exception as e:
            print(f"  FAIL: {e}")
            return 1

        import pyarrow.parquet as pq

        snapshots = sorted(data_dir.glob("acled_*.parquet"))
        total = sum(
            pq.read_metadata(s).num_rows for s in snapshots
        )
        print(
            f"  {total:,} events across "
            f"{len(snapshots)} snapshots → {data_dir}"
        )
        print(f"  ({time.monotonic() - t0:.1f}s)")
        print()
    else:
        snapshots = sorted(raw_dir.glob("acled_*.parquet"))
        if not snapshots:
            print(
                f"FAIL: No ACLED snapshots in {raw_dir}. "
                f"Run without --skip-to first."
            )
            return 1
        print(
            f"[1/4] HARVEST — skipped "
            f"({len(snapshots)} snapshots in {raw_dir})"
        )
        print()

    # ── Step 2: Consolidate ──────────────────────────────────

    store_path = Path(
        "data/consolidated/acled/acled_store.parquet",
    )

    if skip_idx < 2:
        print("[2/4] CONSOLIDATE")
        from datafactory_consolidation.consolidators.acled import (
            AcledConsolidationConfig,
            consolidate_acled,
        )

        cons_config = AcledConsolidationConfig(
            source_dir=raw_dir,
            harvest_ledger_path=Path(
                "provenance/acled/ingestion_ledger.jsonl",
            ),
            output_path=store_path,
            ledger_path=Path(
                "provenance/consolidation/acled_ledger.jsonl",
            ),
        )

        t0 = time.monotonic()
        try:
            result = consolidate_acled(cons_config)
        except Exception as e:
            print(f"  FAIL: {e}")
            return 1

        print(
            f"  {result.n_records_total:,} records "
            f"({result.n_records_new:,} new) → {store_path}"
        )
        print(f"  ({time.monotonic() - t0:.1f}s)")
        print()
    else:
        if not store_path.exists():
            print(
                f"FAIL: Expected {store_path} but not found."
            )
            return 1
        print(
            f"[2/4] CONSOLIDATE — skipped "
            f"(using {store_path})"
        )
        print()

    # ── Step 3: Viewpoint ────────────────────────────────────

    viewpoint_path = Path("data/viewpoint/acled_v1.parquet")

    if skip_idx < 3:
        print("[3/4] VIEWPOINT")
        from datafactory_viewpoint.builders.acled_v1 import (
            AcledViewpointConfig,
            build_acled_v1,
        )

        vp_config = AcledViewpointConfig(
            consolidated_path=store_path,
            output_path=viewpoint_path,
            ledger_path=Path(
                "provenance/viewpoint/acled_v1_ledger.jsonl",
            ),
        )

        t0 = time.monotonic()
        try:
            result = build_acled_v1(vp_config)
        except Exception as e:
            print(f"  FAIL: {e}")
            return 1

        print(
            f"  {result.n_events_output:,} events → "
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
            f"[3/4] VIEWPOINT — skipped "
            f"(using {viewpoint_path})"
        )
        print()

    # ── Step 4: Compile ──────────────────────────────────────

    print("[4/4] COMPILE")
    from datafactory_compilation import compile_grid
    from datafactory_compilation.compilation_config import (
        CompilationConfig,
        FeatureSpec,
    )
    from datafactory_priogrid import GridConfig, TemporalConfig

    output_dir = Path("data/compiled/acled")

    config = CompilationConfig(
        source_path=viewpoint_path,
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
        output_dir=output_dir,
        ledger_path=Path(
            "provenance/compilation/acled_ledger.jsonl",
        ),
        date_field="event_date",
        lat_field="latitude",
        lon_field="longitude",
    )

    t0 = time.monotonic()
    try:
        result_dir = compile_grid(config)
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
    print(f"ACLED PIPELINE COMPLETE ({total:.1f}s)")
    print(f"  Grid: {result_dir / 'grid.npy'}")
    print(f"  Shape: {grid.shape}")
    print()
    print(
        "Next: uv run python scripts/verify_acled_grid.py"
    )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
