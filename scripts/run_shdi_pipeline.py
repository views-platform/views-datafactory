#!/usr/bin/env python3
"""Run the full SHDI pipeline: harvest → viewpoint → compile.

Usage:
    uv run python scripts/run_shdi_pipeline.py
    uv run python scripts/run_shdi_pipeline.py --skip-to compile
    uv run python scripts/run_shdi_pipeline.py --end-year 2024

Consolidation is skipped — SHDI is a single periodic release with
nothing to merge (ADR-036, following ADR-029 precedent). The
viewpoint reads directly from the harvested Parquet.

Requires GDL_API_TOKEN in environment (ADR-026).
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

from datafactory_harvester.pipeline_runner import (
    PipelineStep,
    run_pipeline,
)

STEPS = ("harvest", "viewpoint", "compile")


def main() -> int:
    """Orchestrate the SHDI pipeline end-to-end."""
    parser = argparse.ArgumentParser(
        description="Run full SHDI pipeline (Layers 1, 3, 4)",
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
        default=datetime.datetime.now(tz=datetime.UTC).year,
        help="Temporal range end year (default: current year)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-download even if cached",
    )
    parser.add_argument(
        "--force-no-lock",
        action="store_true",
        help="Bypass the pipeline writer lock (C-316) — only for "
        "deliberate recovery while no pipeline is running",
    )
    args = parser.parse_args()

    from datafactory_provenance import hold_pipeline_lock

    hold_pipeline_lock(force=args.force_no_lock)

    raw_path = Path("data/raw/shdi/shdi_v10.2.parquet")
    crosswalk_path = Path("data/raw/shdi/gdl_to_pgid.parquet")
    viewpoint_path = Path("data/viewpoint/shdi_v1.parquet")
    output_dir = Path("data/compiled/shdi")

    # ── Step closures ───────────────────────────────────────────

    def harvest() -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        config = ShdiConfig()
        result = fetch_shdi(
            config, force_refresh=args.force,
        )
        print(f"  Outcome: {result['outcome']}")
        if "n_rows" in result:
            print(f"  Rows: {result['n_rows']:,}")

    def check_harvest() -> str:
        if not raw_path.exists():
            msg = (
                f"Expected {raw_path} but not found. "
                f"Run without --skip-to first."
            )
            raise FileNotFoundError(msg)
        return f"using {raw_path}"

    def viewpoint() -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        vp_config = ShdiViewpointConfig(
            source_path=raw_path,
            crosswalk_path=crosswalk_path,
            output_path=viewpoint_path,
            ledger_path=Path(
                "provenance/viewpoint/"
                "shdi_v1_ledger.jsonl",
            ),
            end_year=args.end_year,
        )
        result = build_shdi_v1(vp_config)
        print(
            f"  {result.n_events_output:,} rows → "
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
        import importlib.util

        from datafactory_compilation import compile_pregridded
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
        )
        from datafactory_priogrid import (
            GridConfig,
            TemporalConfig,
        )

        _compile_shdi_path = (
            Path(__file__).parent / "compile_shdi.py"
        )
        _spec = importlib.util.spec_from_file_location(
            "compile_shdi", _compile_shdi_path,
        )
        if _spec is None or _spec.loader is None:
            msg = f"Cannot load {_compile_shdi_path}"
            raise FileNotFoundError(msg)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        shdi_features = _mod.SHDI_FEATURES

        config = PregriddedCompilationConfig(
            source_path=viewpoint_path,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                end_year=args.end_year,
            ),
            features=shdi_features,
            output_dir=output_dir,
            ledger_path=Path(
                "provenance/compilation/shdi_ledger.jsonl",
            ),
            fill_value=float("nan"),
        )
        result_dir = compile_pregridded(config)

        import numpy as np

        grid = np.load(result_dir / "grid.npy", mmap_mode="r")
        print(f"  Grid shape: {grid.shape}")
        print(f"  Output: {result_dir}")

    # ── Run pipeline ────────────────────────────────────────────

    pipeline_steps = (
        PipelineStep("harvest", harvest, check_harvest),
        PipelineStep("viewpoint", viewpoint, check_viewpoint),
        PipelineStep("compile", compile_step),
    )

    result = run_pipeline(
        source_name="SHDI",
        steps=pipeline_steps,
        config_summary={
            "Layers": "1, 3, 4",
            "End year": str(args.end_year),
            "Consolidation": "skipped (single release, ADR-036)",
        },
        skip_to=args.skip_to,
    )

    if not result.success:
        return 1

    # ── Summary ─────────────────────────────────────────────────

    print("=" * 60)
    print(f"SHDI PIPELINE COMPLETE ({result.elapsed:.1f}s)")
    print()
    print(
        "Next: uv run python scripts/assemble_grid.py "
        "--shdi-grid data/compiled/shdi"
    )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
