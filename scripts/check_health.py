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
from datetime import UTC, datetime
from pathlib import Path

from datafactory_provenance.health import (
    FRESHNESS_SLO_HOURS,
    SOURCE_SLO,
    check_export_freshness,
    report_ledger,
)
from datafactory_provenance.source_registry import PIPELINE_SOURCES


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

    now = datetime.now(tz=UTC)

    # Ledger locations derived from the source registry
    ledgers = {
        s.name: args.provenance_dir / s.ledger_path
        for s in PIPELINE_SOURCES
        if s.ledger_path is not None
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
    provenance_path = args.data_dir / "assembled" / "provenance.json"
    freshness = check_export_freshness(
        zarr_path, now, provenance_path=provenance_path,
    )
    if not freshness["export_slo_met"]:
        any_issues = True
    if freshness.get("data_boundary_current") is False:
        any_issues = True
    if freshness.get("content_fresh") is False:
        any_issues = True

    # Sentinel check: assembly ran but exports not yet done (C-253)
    sentinel_path = args.data_dir / "assembled" / ".exports_required"
    sentinel_exists = sentinel_path.exists()

    if args.json:
        output = {
            "timestamp": now.isoformat(),
            "healthy": not any_issues,
            "freshness_slo_hours": FRESHNESS_SLO_HOURS,
            "export_age_hours": freshness["export_age_hours"],
            "export_slo_met": freshness["export_slo_met"],
            "content_fresh": freshness.get("content_fresh"),
            "exports_required_sentinel": sentinel_exists,
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

    # Content freshness (digest match)
    content_fresh = freshness.get("content_fresh")
    if content_fresh is True:
        print(
            f"  [{'OK':7s}] "
            f"{'Content freshness':20s} "
            f"zarr digest matches assembly"
        )
    elif content_fresh is False:
        any_issues = True
        print(
            f"! [{'STALE':7s}] "
            f"{'Content freshness':20s} "
            f"zarr digest does NOT match assembly — "
            f"re-export: uv run python scripts/export_zarr.py"
        )

    # Sentinel check
    if sentinel_exists:
        any_issues = True
        print(
            f"! [{'PENDING':7s}] "
            f"{'Export sentinel':20s} "
            f".exports_required present — "
            f"assembly ran but exports not yet done"
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
