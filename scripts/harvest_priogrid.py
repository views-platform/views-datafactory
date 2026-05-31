#!/usr/bin/env python3
"""Layer 1: Harvest PRIO-GRID features from the API.

Usage:
    uv run python scripts/harvest_priogrid.py
    uv run python scripts/harvest_priogrid.py --variables landarea,mountains_mean
    uv run python scripts/harvest_priogrid.py --force

Fetches static PRIO-GRID variables (terrain, resources, land cover)
and stores as Parquet files. One file per variable.

Does NOT consolidate, build viewpoints, or compile to grid.

Local-first: skips variables already on disk with matching digest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datafactory_harvester.harvest_runner import run_harvest


def main() -> int:
    """Run the PRIO-GRID harvester."""
    parser = argparse.ArgumentParser(
        description="Harvest PRIO-GRID features (Layer 1)"
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
        default=Path("data/raw/priogrid_static"),
        help="Output directory",
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=Path("provenance/priogrid_static"),
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

    from datafactory_harvester.sources.priogrid_static import (
        PriogridStaticConfig,
        fetch_priogrid_static,
    )

    config = PriogridStaticConfig(
        data_dir=args.data_dir,
        ledger_path=args.provenance_dir / "ingestion_ledger.jsonl",
        variables=variables,
    )

    result = run_harvest(
        source_name="PRIO-GRID",
        fetch_fn=fetch_priogrid_static,
        config_summary={
            "Variables": str(variables or "all static"),
            "Data dir": str(args.data_dir),
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
    n_fetched = sum(1 for r in results if r.get("outcome") == "success")
    n_unchanged = sum(1 for r in results if r.get("outcome") == "unchanged")
    n_failed = sum(1 for r in results if r.get("outcome") == "failed")

    print("=" * 60)
    print(f"COMPLETE — {result.elapsed:.1f}s")
    print(
        f"  {n_total} variables: "
        f"{n_cached} cached, {n_fetched} fetched, "
        f"{n_unchanged} unchanged, {n_failed} failed"
    )
    for r in results:
        outcome = r.get("outcome", "?")
        name = r.get("variable", "?")
        if outcome == "failed":
            errors = r.get("errors", [])
            print(f"  FAIL: {name} — {errors}")
    print("=" * 60)

    return 1 if n_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
