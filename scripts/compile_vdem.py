#!/usr/bin/env python3
"""Compile V-Dem viewpoint output onto the spatiotemporal grid.

Usage:
    uv run python scripts/compile_vdem.py
    uv run python scripts/compile_vdem.py --source data/viewpoint/vdem_v1.parquet
    uv run python scripts/compile_vdem.py --end-year 2026

Uses pregridded_compilation — V-Dem viewpoint output is already
keyed by (pgid, month_id). No lat/lon lookup needed.

Ref: ADR-035 (V-Dem source selection).
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

VDEM_FEATURES: tuple[PregriddedFeatureSpec, ...] = (
    PregriddedFeatureSpec("vdem_v2xcl_dmove", "v2xcl_dmove"),
    PregriddedFeatureSpec("vdem_v2xeg_eqdr", "v2xeg_eqdr"),
    PregriddedFeatureSpec("vdem_v2xpe_exlsocgr", "v2xpe_exlsocgr"),
    PregriddedFeatureSpec("vdem_v2x_clphy", "v2x_clphy"),
    PregriddedFeatureSpec("vdem_v2xcl_prpty", "v2xcl_prpty"),
    PregriddedFeatureSpec("vdem_v2x_ex_military", "v2x_ex_military"),
    PregriddedFeatureSpec("vdem_v2x_ex_party", "v2x_ex_party"),
    PregriddedFeatureSpec("vdem_v2x_horacc", "v2x_horacc"),
    PregriddedFeatureSpec("vdem_v2xnp_client", "v2xnp_client"),
    PregriddedFeatureSpec("vdem_v2xnp_regcorr", "v2xnp_regcorr"),
    PregriddedFeatureSpec("vdem_v2xpe_exlgeo", "v2xpe_exlgeo"),
    PregriddedFeatureSpec("vdem_v2x_veracc", "v2x_veracc"),
    PregriddedFeatureSpec("vdem_v2xpe_exlpol", "v2xpe_exlpol"),
    PregriddedFeatureSpec("vdem_v2x_diagacc", "v2x_diagacc"),
    PregriddedFeatureSpec("vdem_v2x_divparctrl", "v2x_divparctrl"),
    PregriddedFeatureSpec("vdem_v2xeg_eqprotec", "v2xeg_eqprotec"),
    PregriddedFeatureSpec("vdem_v2x_genpp", "v2x_genpp"),
    PregriddedFeatureSpec("vdem_v2xpe_exlgender", "v2xpe_exlgender"),
    PregriddedFeatureSpec("vdem_v2x_hosabort", "v2x_hosabort"),
    PregriddedFeatureSpec("vdem_v2x_libdem", "v2x_libdem"),
    PregriddedFeatureSpec("vdem_v2xcl_rol", "v2xcl_rol"),
    PregriddedFeatureSpec("vdem_v2x_accountability", "v2x_accountability"),
)


def main() -> int:
    """Compile V-Dem viewpoint output onto the grid."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Compile V-Dem viewpoint output to grid",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/viewpoint/vdem_v1.parquet"),
        help="Viewpoint Parquet path",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/compiled/vdem"),
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
    print("V-Dem COMPILATION")
    print(f"Source: {args.source}")
    print(f"Output: {args.output_dir}")
    print(f"Features: {len(VDEM_FEATURES)}")
    print("=" * 60)
    print()

    config = PregriddedCompilationConfig(
        source_path=args.source,
        grid_config=GridConfig(),
        temporal_config=TemporalConfig(
            end_year=args.end_year,
        ),
        features=VDEM_FEATURES,
        output_dir=args.output_dir,
        ledger_path=Path(
            "provenance/compilation/vdem_ledger.jsonl",
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
