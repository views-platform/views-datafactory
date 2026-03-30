#!/usr/bin/env python3
"""Layer 1: Harvest UCDP data from the API.

Usage:
    uv run python scripts/harvest_ucdp.py                # all sources
    uv run python scripts/harvest_ucdp.py --source dot9  # .9 only
    uv run python scripts/harvest_ucdp.py --source annual --force  # re-fetch

Fetches raw UCDP event data and stores as Parquet snapshots.
Does NOT consolidate, build viewpoints, or compile to grid.

Local-first: skips versions that already exist on disk with a
matching ledger digest. Re-runs are near-instant for cached data.

Requires UCDP_API_TOKEN environment variable.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    """Run the UCDP harvester."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Harvest UCDP data (Layer 1)"
    )
    parser.add_argument(
        "--source",
        choices=["annual", "candidate", "dot9", "all"],
        default="all",
        help="Which source to fetch (default: all)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/raw"),
        help="Raw data directory (default: data/raw/)",
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=Path("provenance"),
        help="Provenance directory (default: provenance/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch even if data exists",
    )
    args = parser.parse_args()

    sources = (
        ["annual", "candidate", "dot9"]
        if args.source == "all"
        else [args.source]
    )

    print("=" * 60)
    print("UCDP HARVESTER (Layer 1)")
    print(f"Sources: {', '.join(sources)}")
    print(f"Data dir: {args.data_dir}")
    print(f"Force refresh: {args.force}")
    print("=" * 60)
    print()

    t_start = time.monotonic()
    results: dict[str, dict] = {}

    if "annual" in sources:
        results["annual"] = _harvest_annual(
            args.data_dir, args.provenance_dir, args.force
        )

    if "candidate" in sources:
        results["candidate"] = _harvest_candidate(
            args.data_dir, args.provenance_dir, args.force
        )

    if "dot9" in sources:
        results["dot9"] = _harvest_dot9(
            args.data_dir, args.provenance_dir, args.force
        )

    total_time = time.monotonic() - t_start

    print()
    print("=" * 60)
    print(f"HARVEST COMPLETE — {total_time:.1f}s")
    for name, res in results.items():
        status = res.get("status", "?")
        detail = res.get("detail", "")
        print(f"  {name}: {status} {detail}")
    print("=" * 60)

    n_failed = sum(
        1 for r in results.values()
        if r.get("status") == "FAIL"
    )
    return 1 if n_failed > 0 else 0


def _harvest_annual(
    data_dir: Path, prov_dir: Path, force: bool
) -> dict:
    """Harvest UCDP annual data."""
    print("[annual] Fetching v25.1 (1989-2024)...")

    from datafactory_harvester.sources.ucdp_annual import (
        UcdpAnnualConfig,
        fetch_ucdp_annual,
    )

    config = UcdpAnnualConfig(
        data_dir=data_dir / "ucdp_annual",
        ledger_path=(
            prov_dir / "ucdp_annual" / "ingestion_ledger.jsonl"
        ),
        timeout=120,  # Annual dataset is large; 30s often insufficient
        page_size=50000,  # API rate-limits after ~40 requests; 50k = 8 pages
    )

    try:
        import pyarrow.parquet as pq

        path = fetch_ucdp_annual(config, force_refresh=force)
        t = pq.read_table(path)
        print(f"[annual] {t.num_rows:,} events — PASS")
        return {
            "status": "PASS",
            "detail": f"({t.num_rows:,} events)",
        }
    except Exception as e:
        print(f"[annual] FAIL: {e}")
        return {"status": "FAIL", "detail": str(e)}


def _harvest_candidate(
    data_dir: Path, prov_dir: Path, force: bool
) -> dict:
    """Harvest UCDP candidate monthly data."""
    print("[candidate] Discovering versions...")

    from datafactory_harvester.sources.ucdp_candidate import (
        UcdpCandidateConfig,
        fetch_ucdp_candidate,
    )

    config = UcdpCandidateConfig(
        data_dir=data_dir / "ucdp_candidate",
        ledger_path=(
            prov_dir
            / "ucdp_candidate"
            / "ingestion_ledger.jsonl"
        ),
    )

    try:
        t0 = time.monotonic()
        results = fetch_ucdp_candidate(
            config, force_refresh=force
        )
        elapsed = time.monotonic() - t0

        n_total = len(results)
        n_cached = sum(
            1
            for r in results
            if r.get("outcome") == "cached"
        )
        n_fetched = sum(
            1
            for r in results
            if r.get("outcome") == "success"
        )
        n_unchanged = sum(
            1
            for r in results
            if r.get("outcome") == "unchanged"
        )
        n_failed = sum(
            1
            for r in results
            if r.get("outcome") == "failed"
        )

        print(
            f"[candidate] {n_total} versions: "
            f"{n_cached} cached, {n_fetched} fetched, "
            f"{n_unchanged} unchanged, {n_failed} failed "
            f"— {elapsed:.1f}s — PASS"
        )
        return {
            "status": "PASS",
            "detail": (
                f"({n_total} versions, "
                f"{n_cached} cached)"
            ),
        }
    except Exception as e:
        print(f"[candidate] FAIL: {e}")
        return {"status": "FAIL", "detail": str(e)}


def _harvest_dot9(
    data_dir: Path, prov_dir: Path, force: bool
) -> dict:
    """Harvest UCDP .9 consolidated monthly data."""
    print("[dot9] Discovering versions...")

    from datafactory_harvester.sources.ucdp_dot9 import (
        UcdpDot9Config,
        fetch_ucdp_dot9,
    )

    config = UcdpDot9Config(
        data_dir=data_dir / "ucdp_dot9",
        ledger_path=(
            prov_dir / "ucdp_dot9" / "ingestion_ledger.jsonl"
        ),
    )

    try:
        t0 = time.monotonic()
        results = fetch_ucdp_dot9(
            config, force_refresh=force
        )
        elapsed = time.monotonic() - t0

        n_total = len(results)
        n_cached = sum(
            1
            for r in results
            if r.get("outcome") == "cached"
        )
        n_fetched = sum(
            1
            for r in results
            if r.get("outcome") == "success"
        )
        n_unchanged = sum(
            1
            for r in results
            if r.get("outcome") == "unchanged"
        )
        n_failed = sum(
            1
            for r in results
            if r.get("outcome") == "failed"
        )

        print(
            f"[dot9] {n_total} versions: "
            f"{n_cached} cached, {n_fetched} fetched, "
            f"{n_unchanged} unchanged, {n_failed} failed "
            f"— {elapsed:.1f}s — PASS"
        )
        return {
            "status": "PASS",
            "detail": (
                f"({n_total} versions, "
                f"{n_cached} cached)"
            ),
        }
    except Exception as e:
        print(f"[dot9] FAIL: {e}")
        return {"status": "FAIL", "detail": str(e)}


if __name__ == "__main__":
    sys.exit(main())
