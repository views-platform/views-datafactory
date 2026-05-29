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
import time

from datafactory_harvester.sources.shdi import ShdiConfig, fetch_shdi


def main() -> int:
    """Harvest SHDI data from GDL API."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Harvest GDL SHDI data from API",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-download even if cached",
    )
    args = parser.parse_args()

    config = ShdiConfig()

    print("=" * 60)
    print("SHDI HARVEST")
    print(f"Version: {config.version}")
    print(f"Variables: {len(config.variables)}")
    print(f"API: {config.download_url}")
    print(f"Output: {config.output_path}")
    print(f"Crosswalk: {config.crosswalk_path}")
    print("=" * 60)
    print()

    t0 = time.monotonic()
    try:
        result = fetch_shdi(config, force_refresh=args.force)
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    elapsed = time.monotonic() - t0
    print(f"Outcome: {result['outcome']}")
    if "n_rows" in result:
        print(f"Rows: {result['n_rows']:,}")
    if "n_regions" in result:
        print(f"Regions: {result['n_regions']:,}")
    if "n_pgids_mapped" in result:
        print(f"Pgids mapped: {result['n_pgids_mapped']:,}")
    print(f"({elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
