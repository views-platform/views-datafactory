#!/usr/bin/env python3
"""Report system health by reading provenance ledgers.

Usage:
    uv run python scripts/check_health.py
    uv run python scripts/check_health.py --data-dir data

Reads all JSONL provenance ledgers and reports:
- Last successful operation per source
- Time since last success
- Any recent failures

Does not modify anything. Read-only diagnostic.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from datafactory_provenance.health import (
    FRESHNESS_SLO_HOURS,
    SOURCE_SLO,
    check_export_freshness,
    report_ledger,
)


def main() -> int:
    """Report system health."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Check datafactory health"
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=Path("provenance"),
        help="Base provenance directory",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Base data directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (for monitoring integration)",
    )
    args = parser.parse_args()

    now = datetime.now(tz=timezone.utc)

    # Known ledger locations
    ledgers = {
        "UCDP Annual": (
            args.provenance_dir
            / "ucdp_annual"
            / "ingestion_ledger.jsonl"
        ),
        "UCDP Candidate": (
            args.provenance_dir
            / "ucdp_candidate"
            / "ingestion_ledger.jsonl"
        ),
        "UCDP .9": (
            args.provenance_dir
            / "ucdp_dot9"
            / "ingestion_ledger.jsonl"
        ),
        "PRIO-GRID Static": (
            args.provenance_dir
            / "priogrid_static"
            / "ingestion_ledger.jsonl"
        ),
        "Consolidation": (
            args.provenance_dir
            / "consolidation"
            / "ledger.jsonl"
        ),
        "Viewpoint": (
            args.provenance_dir
            / "viewpoint"
            / "ledger.jsonl"
        ),
        "Compilation": (
            args.provenance_dir
            / "compilation"
            / "ledger.jsonl"
        ),
        "PRIO-GRID Shapefile": (
            args.provenance_dir
            / "priogrid"
            / "ingestion_ledger.jsonl"
        ),
    }

    results = []
    any_issues = False
    for name, path in ledgers.items():
        slo = SOURCE_SLO.get(name, FRESHNESS_SLO_HOURS)
        result = report_ledger(name, path, now, slo_hours=slo)
        results.append(result)
        if result["status"] not in ("OK", "NO DATA"):
            any_issues = True

    # Export freshness check (ADR-018 SLO)
    zarr_path = args.data_dir / "assembled" / "grid.zarr"
    freshness = check_export_freshness(zarr_path, now)
    if not freshness["export_slo_met"]:
        any_issues = True
    if freshness.get("data_boundary_current") is False:
        any_issues = True

    if args.json:
        output = {
            "timestamp": now.isoformat(),
            "healthy": not any_issues,
            "freshness_slo_hours": FRESHNESS_SLO_HOURS,
            "export_age_hours": freshness["export_age_hours"],
            "export_slo_met": freshness["export_slo_met"],
            "last_valid_month_id": freshness.get(
                "last_valid_month_id"
            ),
            "data_boundary_current": freshness.get(
                "data_boundary_current"
            ),
            "sources": results,
        }
        print(json.dumps(output, indent=2))
        return 1 if any_issues else 0

    print("=" * 60)
    print(f"DATAFACTORY HEALTH — {now.isoformat()[:19]}Z")
    print(f"Freshness SLO: {FRESHNESS_SLO_HOURS}h (ADR-018)")
    print("=" * 60)
    print()

    # Export freshness
    slo_marker = "  " if freshness["export_slo_met"] else "! "
    slo_status = "MET" if freshness["export_slo_met"] else "BREACH"
    print(
        f"{slo_marker}[{slo_status:7s}] "
        f"{'Export freshness':20s} {freshness['detail']}"
    )

    # Data boundary (last month with real UCDP data)
    last_valid = freshness.get("last_valid_month_id")
    boundary_current = freshness.get("data_boundary_current")
    if last_valid is not None:
        if boundary_current:
            print(
                f"  [{'OK':7s}] "
                f"{'Data boundary':20s} "
                f"last_valid_month_id={last_valid}"
            )
        else:
            print(
                f"! [{'STALE':7s}] "
                f"{'Data boundary':20s} "
                f"last_valid_month_id={last_valid} "
                f"— data has not advanced"
            )
    elif freshness["export_slo_met"]:
        print(
            f"? [{'UNKNOWN':7s}] "
            f"{'Data boundary':20s} "
            f"last_valid_month_id missing from zarr attrs"
        )
    print()

    for result in results:
        status = result["status"]
        name = result["name"]
        detail = result["detail"]
        slo_label = result.get("slo", "")

        if status == "OK":
            marker = "  "
        elif status == "NO DATA":
            marker = "? "
        else:
            marker = "! "

        slo_suffix = f" [SLO: {slo_label}]" if slo_label else ""
        print(f"{marker}[{status:7s}] {name:20s} {detail}{slo_suffix}")

    print()
    if any_issues:
        print("Issues detected. Check details above.")
        return 1
    print("All sources healthy. Export SLO met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
