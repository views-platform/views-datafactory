#!/usr/bin/env python3
"""Layer 1: Harvest GHS-POP population grids from JRC.

Usage:
    uv run python scripts/harvest_ghspop.py                 # all 12 epochs
    uv run python scripts/harvest_ghspop.py --epochs 2020   # single epoch
    uv run python scripts/harvest_ghspop.py --force          # re-download

Downloads GHS-POP R2023A GeoTIFF files (~450 MB per epoch) from
the EU Joint Research Centre. Open access, no authentication.
Does NOT build viewpoints or compile to grid.

Ref: ADR-029 (GHS-POP source), ADR-030 (tifffile tooling).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    """Run the GHS-POP harvester."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Harvest GHS-POP population grids (Layer 1)"
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

    from datafactory_harvester.sources.ghspop import (
        GhsPopConfig,
        fetch_ghspop,
    )

    config_kwargs: dict = {
        "data_dir": Path("data/raw/ghspop"),
        "ledger_path": Path(
            "provenance/ghspop/ingestion_ledger.jsonl",
        ),
    }
    if args.epochs is not None:
        config_kwargs["epochs"] = tuple(args.epochs)

    config = GhsPopConfig(**config_kwargs)

    epoch_label = (
        str(args.epochs) if args.epochs
        else "all (1975–2030)"
    )

    print("=" * 60)
    print("GHS-POP HARVEST (Layer 1)")
    print(f"Epochs:  {epoch_label}")
    print(f"Output:  {config.data_dir}")
    print(f"Ledger:  {config.ledger_path}")
    print("=" * 60)
    print()

    t0 = time.monotonic()

    try:
        results = fetch_ghspop(
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
