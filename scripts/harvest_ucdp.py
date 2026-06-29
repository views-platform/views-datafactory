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

from datafactory_harvester.harvest_runner import run_harvest


def _count_outcomes(results: list[dict]) -> dict[str, int]:
    """Count harvest outcomes by category."""
    counts: dict[str, int] = {}
    for key in ("cached", "success", "unchanged", "failed", "not_served"):
        counts[key] = sum(
            1 for r in results if r.get("outcome") == key
        )
    counts["served"] = len(results) - counts["not_served"]
    return counts


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
        1 for r in results.values() if r.get("status") == "FAIL"
    )
    return 1 if n_failed > 0 else 0


def _harvest_annual(
    data_dir: Path, prov_dir: Path, force: bool
) -> dict:
    """Harvest UCDP annual data (with automatic version discovery)."""
    from datafactory_harvester.sources.ucdp_annual import (
        UcdpAnnualConfig,
        fetch_ucdp_annual,
    )

    config = UcdpAnnualConfig(
        data_dir=data_dir / "ucdp_annual",
        ledger_path=prov_dir / "ucdp_annual" / "ingestion_ledger.jsonl",
        timeout=120,
    )

    print(
        f"[annual] Discovering versions "
        f"(current: v{config.version})..."
    )

    r = run_harvest(
        source_name="UCDP Annual",
        fetch_fn=fetch_ucdp_annual,
        config_summary={
            "Baseline version": f"v{config.version}",
            "Range": f"{config.start_year}-{config.end_year}",
            "Note": "discovery may upgrade to a newer version",
        },
        force_refresh=force,
        fetch_kwargs={"config": config},
    )

    if r.outcome == "failed":
        print(f"[annual] FAIL: {r.error}")
        return {"status": "FAIL", "detail": r.error or ""}

    import pyarrow.parquet as pq

    t = pq.read_table(r.data)
    print(f"[annual] {t.num_rows:,} events — PASS")
    return {"status": "PASS", "detail": f"({t.num_rows:,} events)"}


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
        ledger_path=prov_dir / "ucdp_candidate" / "ingestion_ledger.jsonl",
    )

    r = run_harvest(
        source_name="UCDP Candidate",
        fetch_fn=fetch_ucdp_candidate,
        config_summary={},
        force_refresh=force,
        fetch_kwargs={"config": config},
    )

    if r.outcome == "failed":
        print(f"[candidate] FAIL: {r.error}")
        return {"status": "FAIL", "detail": r.error or ""}

    c = _count_outcomes(r.data)
    print(
        f"[candidate] {c['served']} versions served "
        f"({c['not_served']} no longer available): "
        f"{c['cached']} cached, {c['success']} fetched, "
        f"{c['unchanged']} unchanged, {c['failed']} failed "
        f"— {r.elapsed:.1f}s — PASS"
    )
    return {
        "status": "PASS",
        "detail": f"({c['served']} versions, {c['cached']} cached)",
    }


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
        ledger_path=prov_dir / "ucdp_dot9" / "ingestion_ledger.jsonl",
    )

    r = run_harvest(
        source_name="UCDP .9",
        fetch_fn=fetch_ucdp_dot9,
        config_summary={},
        force_refresh=force,
        fetch_kwargs={"config": config},
    )

    if r.outcome == "failed":
        print(f"[dot9] FAIL: {r.error}")
        return {"status": "FAIL", "detail": r.error or ""}

    c = _count_outcomes(r.data)
    print(
        f"[dot9] {c['served']} versions served "
        f"({c['not_served']} no longer available): "
        f"{c['cached']} cached, {c['success']} fetched, "
        f"{c['unchanged']} unchanged, {c['failed']} failed "
        f"— {r.elapsed:.1f}s — PASS"
    )
    return {
        "status": "PASS",
        "detail": f"({c['served']} versions, {c['cached']} cached)",
    }


if __name__ == "__main__":
    sys.exit(main())
