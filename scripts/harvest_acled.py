#!/usr/bin/env python3
"""Layer 1: Harvest ACLED data from the API.

Usage:
    uv run python scripts/harvest_acled.py --proof         # prove API access (1 page)
    uv run python scripts/harvest_acled.py                 # full harvest
    uv run python scripts/harvest_acled.py --force         # re-fetch

Fetches raw ACLED event data and stores as Parquet snapshots.
Does NOT consolidate, build viewpoints, or compile to grid.

Requires ACLED_USERNAME and ACLED_PASSWORD environment variables.
"""

from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    """Run the ACLED harvester."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Harvest ACLED data (Layer 1)"
    )
    parser.add_argument(
        "--proof",
        action="store_true",
        help="Prove API access only (fetch 1 page, no storage)",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2020,
        help="Start year (default: 2020)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2025,
        help="End year (default: 2025)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch even if data exists",
    )
    args = parser.parse_args()

    if args.proof:
        return _proof_of_access(args.start_year, args.end_year)
    else:
        return _full_harvest(
            args.start_year, args.end_year, args.force
        )


def _proof_of_access(start_year: int, end_year: int) -> int:
    """Fetch 1 page to prove API connectivity. No storage."""
    print("=" * 60)
    print("ACLED PROOF OF ACCESS")
    print(f"Date range: {start_year}-01-01 to {end_year}-12-31")
    print("=" * 60)
    print()

    from datafactory_harvester.sources.acled import (
        AcledConfig,
        fetch_paginated,
        get_acled_credentials,
    )

    try:
        username, password = get_acled_credentials()
        print(f"[auth] Username: {username}")
    except ValueError as e:
        print(f"[auth] FAIL: {e}")
        return 1

    config = AcledConfig(
        start_year=start_year,
        end_year=end_year,
    )

    print("[fetch] Requesting 1 page from ACLED API...")
    t0 = time.monotonic()

    try:
        events = fetch_paginated(
            config, username, password, max_pages=1
        )
    except Exception as e:
        print(f"[fetch] FAIL: {e}")
        return 1

    elapsed = time.monotonic() - t0
    print(f"[fetch] Got {len(events)} events in {elapsed:.1f}s")
    print()

    if not events:
        print("WARNING: API returned 0 events. Check date range.")
        return 1

    print("Sample events:")
    for ev in events[:3]:
        print(
            f"  {ev.get('event_id_cnty', '?'):>12} | "
            f"{ev.get('event_date', '?')} | "
            f"{ev.get('country', '?')} | "
            f"{ev.get('event_type', '?')}"
        )
    if len(events) > 3:
        print(f"  ... and {len(events) - 3} more")

    print()
    print("=" * 60)
    print(
        f"ACCESS VERIFIED: fetched {len(events)} events "
        f"from ACLED API"
    )
    print("=" * 60)
    return 0


def _full_harvest(
    start_year: int, end_year: int, force: bool
) -> int:
    """Run the full ACLED harvest pipeline."""
    from pathlib import Path

    from datafactory_harvester.sources.acled import (
        AcledConfig,
        fetch_acled,
    )

    print("=" * 60)
    print("ACLED HARVESTER (Layer 1)")
    print(f"Date range: {start_year}-01-01 to {end_year}-12-31")
    print(f"Force refresh: {force}")
    print("=" * 60)
    print()

    config = AcledConfig(
        start_year=start_year,
        end_year=end_year,
        data_dir=Path("data/raw/acled"),
        ledger_path=Path(
            "provenance/acled/ingestion_ledger.jsonl"
        ),
    )

    t0 = time.monotonic()
    try:
        data_dir = fetch_acled(config, force_refresh=force)
    except Exception as e:
        print(f"[harvest] FAIL: {e}")
        return 1

    elapsed = time.monotonic() - t0

    import pyarrow.parquet as pq

    snapshots = sorted(data_dir.glob("acled_*.parquet"))
    total_events = 0
    for snap in snapshots:
        n = pq.read_metadata(snap).num_rows
        total_events += n
        print(f"  {snap.name}: {n:,} events")
    print(
        f"[harvest] {total_events:,} events across "
        f"{len(snapshots)} snapshots in {data_dir}"
    )
    print(f"[harvest] Completed in {elapsed:.1f}s — PASS")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
