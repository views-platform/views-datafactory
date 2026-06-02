#!/usr/bin/env python3
"""Harvest V-Dem country-year data.

Usage:
    uv run python scripts/harvest_vdem.py
    uv run python scripts/harvest_vdem.py --force

Downloads V-Dem v16 CSV, filters to 22 production variables,
stores as Parquet. No authentication required.

Ref: ADR-035 (V-Dem source selection).
"""

from __future__ import annotations

import argparse
import sys

from datafactory_harvester.harvest_runner import run_harvest
from datafactory_harvester.sources.vdem import VdemConfig, fetch_vdem


def main() -> int:
    """Harvest V-Dem data."""
    parser = argparse.ArgumentParser(
        description="Harvest V-Dem country-year data",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-download even if cached",
    )
    args = parser.parse_args()

    config = VdemConfig()
    result = run_harvest(
        source_name="V-Dem",
        fetch_fn=fetch_vdem,
        config_summary={
            "Version": config.version,
            "Variables": str(len(config.variables)),
            "Output": str(config.output_path),
        },
        force_refresh=args.force,
        fetch_kwargs={"config": config},
    )

    if result.outcome == "failed":
        return 1

    print(f"Outcome: {result.data['outcome']}")
    if "n_rows" in result.data:
        print(f"Rows: {result.data['n_rows']:,}")
    print(f"({result.elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
