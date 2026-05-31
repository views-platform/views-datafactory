#!/usr/bin/env python3
"""Harvest GDL Subnational HDI (SHDI) data.

Usage:
    uv run python scripts/harvest_shdi.py
    uv run python scripts/harvest_shdi.py --force

Downloads SHDI data from the GDL Data API and GDL shapefiles
from PRIO CDN. Requires GDL_API_TOKEN environment variable
(free account at globaldatalab.org → My GDL → API Access).

Ref: ADR-036 (SHDI source selection).
"""

from __future__ import annotations

import argparse
import sys

from datafactory_harvester.harvest_runner import run_harvest
from datafactory_harvester.sources.shdi import ShdiConfig, fetch_shdi


def main() -> int:
    """Harvest SHDI data from GDL API."""
    parser = argparse.ArgumentParser(
        description="Harvest GDL SHDI data from API",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-download even if cached",
    )
    args = parser.parse_args()

    config = ShdiConfig()
    result = run_harvest(
        source_name="SHDI",
        fetch_fn=fetch_shdi,
        config_summary={
            "Version": config.version,
            "Variables": ", ".join(config.variables),
            "API": f"{config.api_base_url}/shdi/download/<indicator>/",
            "Output": str(config.output_path),
            "Crosswalk": str(config.crosswalk_path),
        },
        force_refresh=args.force,
        fetch_kwargs={"config": config},
    )

    if result.outcome == "failed":
        return 1

    print(f"Outcome: {result.data['outcome']}")
    if "n_rows" in result.data:
        print(f"Rows: {result.data['n_rows']:,}")
    if "n_regions" in result.data:
        print(f"Regions: {result.data['n_regions']:,}")
    if "n_pgids_mapped" in result.data:
        print(f"Pgids mapped: {result.data['n_pgids_mapped']:,}")
    print(f"({result.elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
