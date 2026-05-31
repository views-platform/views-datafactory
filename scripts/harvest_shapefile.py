#!/usr/bin/env python3
"""Layer 1: Harvest PRIO-GRID reference shapefile from PRIO.

Usage:
    uv run python scripts/harvest_shapefile.py
    uv run python scripts/harvest_shapefile.py --force

Downloads the PRIO-GRID shapefile ZIP (cell + centroid geometries)
and extracts it. Required by the GAUL admin harvester for spatial
joins against grid centroids.

Local-first: skips if .shp files already exist on disk.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datafactory_harvester.harvest_runner import run_harvest


def main() -> int:
    """Run the PRIO-GRID shapefile harvester."""
    parser = argparse.ArgumentParser(
        description="Harvest PRIO-GRID shapefile (Layer 1)"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/raw/priogrid"),
        help="Output directory (shapefile extracted into data-dir/shapefile/)",
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=Path("provenance/priogrid"),
        help="Provenance directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if cached",
    )
    args = parser.parse_args()

    from datafactory_priogrid.shapefile_harvester import (
        ShapefileHarvesterConfig,
        fetch_shapefile,
    )

    config = ShapefileHarvesterConfig(
        data_dir=args.data_dir,
        ledger_path=args.provenance_dir / "ingestion_ledger.jsonl",
    )

    result = run_harvest(
        source_name="PRIO-GRID SHAPEFILE",
        fetch_fn=fetch_shapefile,
        config_summary={
            "Data dir": str(args.data_dir),
            "Force": str(args.force),
        },
        force_refresh=args.force,
        fetch_kwargs={"config": config},
    )

    if result.outcome == "failed":
        return 1

    shp_dir = result.data
    centroid = shp_dir / "priogrid_centroid.shp"
    cell = shp_dir / "priogrid_cell.shp"

    print("=" * 60)
    print(f"COMPLETE — {result.elapsed:.1f}s")
    print(f"Centroid shapefile: {centroid}")
    print(f"  exists: {centroid.exists()}")
    print(f"Cell shapefile:     {cell}")
    print(f"  exists: {cell.exists()}")
    print("=" * 60)

    if not centroid.exists():
        print("FAIL: centroid shapefile not found after extraction")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
