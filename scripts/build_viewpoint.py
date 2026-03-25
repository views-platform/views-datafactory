#!/usr/bin/env python3
"""Layer 3: Build a UCDP viewpoint from the consolidated event store.

Usage:
    uv run python scripts/build_viewpoint.py
    uv run python scripts/build_viewpoint.py --profile production_parity
    uv run python scripts/build_viewpoint.py --store data/consolidated/store.parquet

Applies survivorship rules, temporal distribution, and filtering to
produce a single-perspective materialized view of the consolidated data.

Does NOT fetch data, consolidate, or compile to grid.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    """Build a UCDP viewpoint."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Build UCDP viewpoint (Layer 3)"
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=Path("data/consolidated/ucdp_store.parquet"),
        help="Consolidated store path",
    )
    parser.add_argument(
        "--profile",
        default="production_parity",
        help="Viewpoint profile name (default: production_parity)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: data/viewpoints/<profile>.parquet)",
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=Path("provenance"),
        help="Provenance directory",
    )
    args = parser.parse_args()

    output = args.output or (
        Path("data/viewpoint") / f"{args.profile}.parquet"
    )

    print("=" * 60)
    print("UCDP VIEWPOINT BUILDER (Layer 3)")
    print(f"Store: {args.store}")
    print(f"Profile: {args.profile}")
    print(f"Output: {output}")
    print("=" * 60)
    print()

    if not args.store.exists():
        print(
            f"FAIL: Consolidated store not found: {args.store}"
        )
        print(
            "Run scripts/consolidate_ucdp.py first."
        )
        return 1

    from datafactory_viewpoint.builders.ucdp_v1 import (
        build_ucdp_v1,
    )
    from datafactory_viewpoint.profiles import load_profile

    config = load_profile(
        args.profile,
        args.store,
        output_path=output,
        ledger_path=(
            args.provenance_dir
            / "viewpoint"
            / "ledger.jsonl"
        ),
    )

    print(
        f"Survivorship: {config.survivorship_strategy}"
    )
    print(
        f"Distribution: {config.distribution_strategy}"
    )
    print()

    t0 = time.monotonic()
    try:
        result = build_ucdp_v1(config)
        elapsed = time.monotonic() - t0

        print(f"Events in: {result.n_events_input:,}")
        print(f"Rows out: {result.n_events_output:,}")
        print(
            f"Summary expanded: {result.n_summary_expanded}"
        )
        print(f"Filtered: {result.n_filtered}")
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
