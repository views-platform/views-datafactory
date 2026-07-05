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
import datetime
import os
import sys
from pathlib import Path

from datafactory_harvester.pipeline_runner import (
    PipelineStep,
    run_pipeline,
)

STEPS = ("harvest", "consolidate", "viewpoint", "compile")


def main() -> int:
    """Orchestrate the ACLED pipeline end-to-end."""
    parser = argparse.ArgumentParser(
        description="Run full ACLED pipeline (Layers 1–4)",
    )
    parser.add_argument(
        "--start-year", type=int, default=2020,
        help="Harvest start year (default: 2020)",
    )
    parser.add_argument(
        "--end-year", type=int, default=datetime.datetime.now(tz=datetime.UTC).year,
        help="Harvest end year (default: current year)",
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

    raw_dir = Path("data/raw/acled")
    store_path = Path(
        "data/consolidated/acled/acled_store.parquet",
    )
    viewpoint_path = Path("data/viewpoint/acled_v1.parquet")
    output_dir = Path("data/compiled/acled")

    # ── Step closures ───────────────────────────────────────────

    def harvest() -> None:
        if (
            not os.environ.get("ACLED_USERNAME")
            or not os.environ.get("ACLED_PASSWORD")
        ):
            msg = (
                "Set ACLED_USERNAME and ACLED_PASSWORD "
                "environment variables."
            )
            raise ValueError(msg)

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
        data_dir = fetch_acled(
            config, force_refresh=args.force,
        )

        import pyarrow.parquet as pq

        snapshots = sorted(data_dir.glob("acled_*.parquet"))
        total = sum(
            pq.read_metadata(s).num_rows for s in snapshots
        )
        print(
            f"  {total:,} events across "
            f"{len(snapshots)} snapshots → {data_dir}"
        )

    def check_harvest() -> str:
        snapshots = sorted(raw_dir.glob("acled_*.parquet"))
        if not snapshots:
            msg = (
                f"No ACLED snapshots in {raw_dir}. "
                f"Run without --skip-to first."
            )
            raise FileNotFoundError(msg)
        return f"{len(snapshots)} snapshots in {raw_dir}"

    def consolidate() -> None:
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
        result = consolidate_acled(cons_config)
        print(
            f"  {result.n_records_total:,} records "
            f"({result.n_records_new:,} new) → {store_path}"
        )

    def check_consolidate() -> str:
        if not store_path.exists():
            msg = f"Expected {store_path} but not found."
            raise FileNotFoundError(msg)
        return f"using {store_path}"

    def viewpoint() -> None:
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
        result = build_acled_v1(vp_config)
        print(
            f"  {result.n_events_output:,} events → "
            f"{viewpoint_path}"
        )

    def check_viewpoint() -> str:
        if not viewpoint_path.exists():
            msg = (
                f"Expected {viewpoint_path} but not found."
            )
            raise FileNotFoundError(msg)
        return f"using {viewpoint_path}"

    def compile_step() -> None:
        from datafactory_compilation import compile_grid
        from datafactory_compilation.compilation_config import (
            CompilationConfig,
            FeatureSpec,
        )
        from datafactory_priogrid import (
            GridConfig,
            TemporalConfig,
        )

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
        result_dir = compile_grid(config)

        import numpy as np

        grid = np.load(result_dir / "grid.npy", mmap_mode="r")
        print(f"  Grid shape: {grid.shape}")
        print(f"  Output: {result_dir}")

    # ── Run pipeline ────────────────────────────────────────────

    pipeline_steps = (
        PipelineStep("harvest", harvest, check_harvest),
        PipelineStep(
            "consolidate", consolidate, check_consolidate,
        ),
        PipelineStep("viewpoint", viewpoint, check_viewpoint),
        PipelineStep("compile", compile_step),
    )

    result = run_pipeline(
        source_name="ACLED",
        steps=pipeline_steps,
        config_summary={
            "Layers": "1–4",
            "Range": f"{args.start_year}–{args.end_year}",
        },
        skip_to=args.skip_to,
    )

    if not result.success:
        return 1

    print("=" * 60)
    print(f"ACLED PIPELINE COMPLETE ({result.elapsed:.1f}s)")
    print()
    print(
        "Next: uv run python scripts/verify_acled_grid.py"
    )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
