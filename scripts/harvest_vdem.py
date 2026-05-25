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
import time

from datafactory_harvester.sources.vdem import VdemConfig, fetch_vdem


def main() -> int:
    """Harvest V-Dem data."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Harvest V-Dem country-year data",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-download even if cached",
    )
    args = parser.parse_args()

    config = VdemConfig()

    print("=" * 60)
    print("V-Dem HARVEST")
    print(f"Version: {config.version}")
    print(f"Variables: {len(config.variables)}")
    print(f"Output: {config.output_path}")
    print("=" * 60)
    print()

    t0 = time.monotonic()
    try:
        result = fetch_vdem(config, force_refresh=args.force)
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    elapsed = time.monotonic() - t0
    print(f"Outcome: {result['outcome']}")
    if "n_rows" in result:
        print(f"Rows: {result['n_rows']:,}")
    print(f"({elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
