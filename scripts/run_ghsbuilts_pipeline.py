#!/usr/bin/env python3
"""Run the full GHS-BUILT-S pipeline: harvest → viewpoint → compile.

Usage:
    uv run python scripts/run_ghsbuilts_pipeline.py
    uv run python scripts/run_ghsbuilts_pipeline.py --skip-to compile
    uv run python scripts/run_ghsbuilts_pipeline.py --epochs 2020 2025
    uv run python scripts/run_ghsbuilts_pipeline.py --end-year 2026
    uv run python scripts/run_ghsbuilts_pipeline.py --verify

Consolidation is skipped — GHS-BUILT-S R2023A is a single release with
nothing to merge (ADR-034). The viewpoint reads directly from the
harvested GeoTIFF files.

No authentication required — JRC data is open access.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from datafactory_harvester.pipeline_runner import (
    PipelineStep,
    run_pipeline,
)

STEPS = ("harvest", "viewpoint", "compile")


def main() -> int:
    """Orchestrate the GHS-BUILT-S pipeline end-to-end."""
    parser = argparse.ArgumentParser(
        description=(
            "Run full GHS-BUILT-S pipeline (Layers 1, 3, 4)"
        ),
    )
    parser.add_argument(
        "--epochs",
        type=int,
        nargs="+",
        default=None,
        help=(
            "GHS-BUILT-S epochs to process "
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
    parser.add_argument(
        "--verify", action="store_true",
        help="Run visual audit after compilation",
    )
    args = parser.parse_args()

    raw_dir = Path("data/raw/ghsbuilts")
    viewpoint_path = Path("data/viewpoint/ghsbuilts_v1.parquet")
    output_dir = Path("data/compiled/ghsbuilts")

    # ── Step closures ───────────────────────────────────────────

    def harvest() -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        harvest_kwargs: dict = {}
        if args.epochs is not None:
            harvest_kwargs["epochs"] = tuple(args.epochs)

        config = GhsBuiltSConfig(
            data_dir=raw_dir,
            ledger_path=Path(
                "provenance/ghsbuilts/ingestion_ledger.jsonl",
            ),
            **harvest_kwargs,
        )
        results = fetch_ghsbuilts(
            config, force_refresh=args.force,
        )
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

    def check_harvest() -> str:
        tif_files = sorted(raw_dir.glob("*.tif"))
        if not tif_files:
            msg = (
                f"No GeoTIFF files in {raw_dir}. "
                f"Run without --skip-to first."
            )
            raise FileNotFoundError(msg)
        return f"{len(tif_files)} GeoTIFFs in {raw_dir}"

    def viewpoint() -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
            build_ghsbuilts_v1,
        )

        vp_kwargs: dict = {}
        if args.epochs is not None:
            vp_kwargs["epochs"] = tuple(args.epochs)

        vp_config = GhsBuiltSViewpointConfig(
            source_dir=raw_dir,
            output_path=viewpoint_path,
            ledger_path=Path(
                "provenance/viewpoint/"
                "ghsbuilts_v1_ledger.jsonl",
            ),
            **vp_kwargs,
        )
        result = build_ghsbuilts_v1(vp_config)
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
        from datafactory_compilation import compile_pregridded
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )
        from datafactory_priogrid import (
            GridConfig,
            TemporalConfig,
        )

        config = PregriddedCompilationConfig(
            source_path=viewpoint_path,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                end_year=args.end_year,
            ),
            features=(
                PregriddedFeatureSpec(
                    "ghsbuilts_built_area", "built_area",
                ),
            ),
            output_dir=output_dir,
            ledger_path=Path(
                "provenance/compilation/ghsbuilts_ledger.jsonl",
            ),
        )
        result_dir = compile_pregridded(config)

        import numpy as np

        grid = np.load(result_dir / "grid.npy", mmap_mode="r")
        print(f"  Grid shape: {grid.shape}")
        print(f"  Output: {result_dir}")

    # ── Run pipeline ────────────────────────────────────────────

    epoch_label = (
        str(args.epochs) if args.epochs
        else "all (1975–2030)"
    )

    pipeline_steps = (
        PipelineStep("harvest", harvest, check_harvest),
        PipelineStep("viewpoint", viewpoint, check_viewpoint),
        PipelineStep("compile", compile_step),
    )

    result = run_pipeline(
        source_name="GHS-BUILT-S",
        steps=pipeline_steps,
        config_summary={
            "Layers": "1, 3, 4",
            "Epochs": epoch_label,
            "End year": str(args.end_year),
            "Consolidation": "skipped (single release, ADR-034)",
        },
        skip_to=args.skip_to,
    )

    if not result.success:
        return 1

    # ── Optional verify ─────────────────────────────────────────

    if args.verify:
        print("[VERIFY]")
        t0 = time.monotonic()
        rc = subprocess.run(
            [
                sys.executable,
                "scripts/verify_ghsbuilts_grid.py",
                "--input", str(output_dir),
            ],
            check=False,
        ).returncode
        print(f"  ({time.monotonic() - t0:.1f}s)")
        if rc != 0:
            print("  FAIL: verify script exited non-zero")
            return 1
        print()

    # ── Summary ─────────────────────────────────────────────────

    print("=" * 60)
    print(
        f"GHS-BUILT-S PIPELINE COMPLETE "
        f"({result.elapsed:.1f}s)"
    )
    print()
    print(
        "Next: uv run python scripts/assemble_grid.py "
        "--ghsbuilts-grid data/compiled/ghsbuilts"
    )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
