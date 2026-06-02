#!/usr/bin/env python3
"""Layer 1: Harvest GAUL 2024 admin boundaries from FAO.

Usage:
    uv run python scripts/harvest_gaul.py
    uv run python scripts/harvest_gaul.py --variables gaul0_code,gaul1_code
    uv run python scripts/harvest_gaul.py --force

Downloads GAUL 2024 shapefiles from FAO, performs a spatial join
against PRIO-GRID centroids, and stores per-variable Parquet files.

Variables produced:
    gaul0_code  — GAUL country code (int)
    gaul0_name  — GAUL country name (str)
    gaul1_code  — GAUL admin-1 code (int)
    gaul1_name  — GAUL admin-1 name (str)
    gaul2_code  — GAUL admin-2 code (int)
    gaul2_name  — GAUL admin-2 name (str)

Each stored as Parquet with columns (gid, value), matching the
priogrid_static pattern for assembly into the grid.

Local-first: skips if all variables already cached with digests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datafactory_harvester.harvest_runner import run_harvest


def main() -> int:
    """Run the GAUL admin boundary harvester."""
    parser = argparse.ArgumentParser(
        description="Harvest GAUL admin boundaries (Layer 1)"
    )
    parser.add_argument(
        "--variables",
        type=str,
        default=None,
        help="Comma-separated variable names (default: all)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/raw/gaul_admin"),
        help="Output directory for Parquet files",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/raw/gaul_admin/shapefiles"),
        help="Cache directory for downloaded shapefiles",
    )
    parser.add_argument(
        "--centroid-shapefile",
        type=Path,
        default=Path(
            "data/raw/priogrid/shapefile/priogrid_centroid.shp"
        ),
        help="PRIO-GRID centroid shapefile",
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=Path("provenance/gaul_admin"),
        help="Provenance directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch even if cached",
    )
    args = parser.parse_args()

    variables = (
        tuple(args.variables.split(",")) if args.variables else None
    )

    from datafactory_harvester.sources.gaul_admin import (
        GaulAdminConfig,
        fetch_gaul_admin,
    )

    config = GaulAdminConfig(
        data_dir=args.data_dir,
        cache_dir=args.cache_dir,
        centroid_shapefile=args.centroid_shapefile,
        ledger_path=args.provenance_dir / "ingestion_ledger.jsonl",
        variables=variables,
    )

    result = run_harvest(
        source_name="GAUL ADMIN BOUNDARY",
        fetch_fn=fetch_gaul_admin,
        config_summary={
            "Variables": str(variables or "all 6"),
            "Data dir": str(args.data_dir),
            "Cache dir": str(args.cache_dir),
            "Centroids": str(args.centroid_shapefile),
            "Force": str(args.force),
        },
        force_refresh=args.force,
        fetch_kwargs={"config": config},
    )

    if result.outcome == "failed":
        return 1

    results = result.data
    n_total = len(results)
    n_cached = sum(1 for r in results if r.get("outcome") == "cached")
    n_success = sum(1 for r in results if r.get("outcome") == "success")
    n_unchanged = sum(1 for r in results if r.get("outcome") == "unchanged")
    n_failed = sum(1 for r in results if r.get("outcome") == "failed")

    print("=" * 60)
    print(f"COMPLETE — {result.elapsed:.1f}s")
    print(
        f"  {n_total} variables: "
        f"{n_cached} cached, {n_success} success, "
        f"{n_unchanged} unchanged, {n_failed} failed"
    )
    for r in results:
        outcome = r.get("outcome", "?")
        name = r.get("variable", "?")
        n_cells = r.get("n_cells", "")
        n_fb = r.get("n_from_fallback", 0)
        if outcome == "success":
            fb_str = f" ({n_fb} from L1 fallback)" if n_fb else ""
            print(f"  OK: {name} — {n_cells} cells{fb_str}")
        elif outcome == "failed":
            errors = r.get("errors", [])
            print(f"  FAIL: {name} — {errors}")
        elif outcome == "cached":
            print(f"  CACHED: {name}")
    print("=" * 60)

    return 1 if n_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
