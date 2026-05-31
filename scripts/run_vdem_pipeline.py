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
    """Orchestrate the V-Dem pipeline end-to-end."""
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
    parser.add_argument(
        "--verify", action="store_true",
        help="Run visual audit after compilation",
    )
    args = parser.parse_args()

    raw_path = Path("data/raw/vdem/vdem_v16.parquet")
    viewpoint_path = Path("data/viewpoint/vdem_v1.parquet")
    output_dir = Path("data/compiled/vdem")

    # ── Step closures ───────────────────────────────────────────

    def harvest() -> None:
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        config = VdemConfig()
        result = fetch_vdem(
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
        result = build_vdem_v1(vp_config)
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

        _compile_vdem_path = (
            Path(__file__).parent / "compile_vdem.py"
        )
        _spec = importlib.util.spec_from_file_location(
            "compile_vdem", _compile_vdem_path,
        )
        if _spec is None or _spec.loader is None:
            msg = f"Cannot load {_compile_vdem_path}"
            raise FileNotFoundError(msg)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        vdem_features = _mod.VDEM_FEATURES

        config = PregriddedCompilationConfig(
            source_path=viewpoint_path,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                end_year=args.end_year,
            ),
            features=vdem_features,
            output_dir=output_dir,
            ledger_path=Path(
                "provenance/compilation/vdem_ledger.jsonl",
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
        source_name="V-Dem",
        steps=pipeline_steps,
        config_summary={
            "Layers": "1, 3, 4",
            "End year": str(args.end_year),
            "Consolidation": "skipped (single release, ADR-035)",
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
                str(
                    Path(__file__).parent
                    / "verify_vdem_grid.py"
                ),
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
    print(f"V-Dem PIPELINE COMPLETE ({result.elapsed:.1f}s)")
    print()
    print(
        "Next: uv run python scripts/assemble_grid.py "
        "--vdem-grid data/compiled/vdem"
    )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
