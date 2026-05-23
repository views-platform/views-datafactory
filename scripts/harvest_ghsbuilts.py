#!/usr/bin/env python3
"""Layer 1: Harvest GHS-BUILT-S built-up surface grids from JRC.

Usage:
    uv run python scripts/harvest_ghsbuilts.py                 # all 12 epochs
    uv run python scripts/harvest_ghsbuilts.py --epochs 2020   # single epoch
    uv run python scripts/harvest_ghsbuilts.py --force          # re-download

Downloads GHS-BUILT-S R2023A GeoTIFF files (~450 MB per epoch) from
the EU Joint Research Centre. Open access, no authentication.
Does NOT build viewpoints or compile to grid.

Ref: ADR-034 (GHS-BUILT-S source), ADR-030 (tifffile tooling).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    """Run the GHS-BUILT-S harvester."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Harvest GHS-BUILT-S built-up surface grids (Layer 1)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        nargs="+",
        default=None,
        help=(
            "Epochs to download "
            "(default: all 12 epochs 1975–2030)"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if cached",
    )
    args = parser.parse_args()

    from datafactory_harvester.sources.ghsbuilts import (
        GhsBuiltSConfig,
        fetch_ghsbuilts,
    )

    config_kwargs: dict = {
        "data_dir": Path("data/raw/ghsbuilts"),
        "ledger_path": Path(
            "provenance/ghsbuilts/ingestion_ledger.jsonl",
        ),
    }
    if args.epochs is not None:
        config_kwargs["epochs"] = tuple(args.epochs)

    config = GhsBuiltSConfig(**config_kwargs)

    epoch_label = (
        str(args.epochs) if args.epochs
        else "all (1975–2030)"
    )

    print("=" * 60)
    print("GHS-BUILT-S HARVEST (Layer 1)")
    print(f"Epochs:  {epoch_label}")
    print(f"Output:  {config.data_dir}")
    print(f"Ledger:  {config.ledger_path}")
    print("=" * 60)
    print()

    t0 = time.monotonic()

    try:
        results = fetch_ghsbuilts(
            config, force_refresh=args.force,
        )
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    n_cached = sum(
        1 for r in results if r["outcome"] == "cached"
    )
    n_new = sum(
        1 for r in results if r["outcome"] == "success"
    )

    elapsed = time.monotonic() - t0
    print()
    print(
        f"{len(results)} epochs: "
        f"{n_new} downloaded, {n_cached} cached"
    )
    print(f"Output: {config.data_dir}")
    print(f"Time: {elapsed:.1f}s")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
