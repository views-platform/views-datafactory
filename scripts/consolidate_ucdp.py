#!/usr/bin/env python3
"""Layer 2: Consolidate UCDP raw snapshots into a lossless event store.

Usage:
    uv run python scripts/consolidate_ucdp.py
    uv run python scripts/consolidate_ucdp.py --data-dir data/raw

Reads whatever Parquet files exist in the annual, candidate, and .9
directories, tags each with source metadata, deduplicates on content
digest (ADR-017), and writes a single consolidated Parquet store.

Does NOT fetch data or build viewpoints.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    """Run UCDP consolidation."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Consolidate UCDP data (Layer 2)"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/raw"),
        help="Raw data directory (default: data/raw/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/consolidated"),
        help="Output directory (default: data/consolidated/)",
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=Path("provenance"),
        help="Provenance directory (default: provenance/)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("UCDP CONSOLIDATION (Layer 2)")
    print(f"Data dir: {args.data_dir}")
    print(f"Output:   {args.output_dir}")
    print("=" * 60)
    print()

    from datafactory_consolidation.consolidators.ucdp import (
        UcdpConsolidationConfig,
        consolidate_ucdp,
    )

    config = UcdpConsolidationConfig(
        annual_dir=args.data_dir / "ucdp_annual",
        candidate_dir=args.data_dir / "ucdp_candidate",
        dot9_dir=args.data_dir / "ucdp_dot9",
        annual_ledger_path=(
            args.provenance_dir
            / "ucdp_annual"
            / "ingestion_ledger.jsonl"
        ),
        candidate_ledger_path=(
            args.provenance_dir
            / "ucdp_candidate"
            / "ingestion_ledger.jsonl"
        ),
        dot9_ledger_path=(
            args.provenance_dir
            / "ucdp_dot9"
            / "ingestion_ledger.jsonl"
        ),
        output_path=(
            args.output_dir / "ucdp_store.parquet"
        ),
        ledger_path=(
            args.provenance_dir
            / "consolidation"
            / "ledger.jsonl"
        ),
    )

    # Count source files
    for label, d in [
        ("annual", config.annual_dir),
        ("candidate", config.candidate_dir),
        ("dot9", config.dot9_dir),
    ]:
        n = (
            len(list(d.glob("*.parquet")))
            if d.exists()
            else 0
        )
        print(f"  {label}: {n} files")

    t0 = time.monotonic()
    try:
        result = consolidate_ucdp(config)
        elapsed = time.monotonic() - t0

        print()
        print(f"Total records: {result.n_records_total:,}")
        print(f"New records: {result.n_records_new:,}")
        print(f"Sources: {result.n_sources}")
        print(f"Output: {result.output_path}")
        print(f"Digest: {result.output_digest}")
        print(f"Time: {elapsed:.1f}s")
        print("PASS")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
