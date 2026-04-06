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

# Freshness SLO: maximum acceptable age of exported data (ADR-018).
# Monthly pipeline runs on the 21st. 7 days (168h) allows one missed
# cycle before data is flagged as stale.
FRESHNESS_SLO_HOURS = 168


def _read_last_entries(
    ledger_path: Path, n: int = 5
) -> list[dict]:
    """Read last N entries from a JSONL ledger."""
    if not ledger_path.exists():
        return []
    lines = ledger_path.read_text().strip().splitlines()
    entries = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(entries) >= n:
            break
    return entries


def _report_ledger(
    name: str, ledger_path: Path, now: datetime
) -> dict:
    """Report health for one ledger."""
    entries = _read_last_entries(ledger_path, n=10)

    if not entries:
        return {
            "name": name,
            "status": "NO DATA",
            "detail": f"Ledger not found: {ledger_path}",
        }

    # Find last success. Some ledgers (consolidation, viewpoint,
    # compilation) don't have an "outcome" field — entries only
    # exist for successful operations (failures raise exceptions).
    last_success = None
    for entry in entries:
        outcome = entry.get("outcome")
        if outcome is None or outcome in (
            "success", "unchanged", "cached"
        ):
            last_success = entry
            break

    # Find recent failures
    recent_failures = [
        e for e in entries
        if e.get("outcome") == "failed"
    ]

    if last_success:
        ts_str = last_success.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
            age = now - ts
            age_hours = age.total_seconds() / 3600
            age_str = (
                f"{age_hours:.0f}h ago"
                if age_hours < 48
                else f"{age_hours / 24:.0f}d ago"
            )
        except (ValueError, TypeError):
            age_str = "unknown"
            age_hours = -1

        status = "OK" if age_hours < FRESHNESS_SLO_HOURS else "STALE"
        detail = (
            f"Last success: {ts_str[:19]} ({age_str})"
        )
        if recent_failures:
            detail += (
                f" | {len(recent_failures)} recent failures"
            )

        return {
            "name": name,
            "status": status,
            "detail": detail,
            "version": last_success.get("version", ""),
            "digest": last_success.get(
                "content_digest",
                last_success.get("output_digest", ""),
            ),
        }

    return {
        "name": name,
        "status": "FAILING",
        "detail": (
            f"No successful entries in last 10. "
            f"{len(recent_failures)} failures."
        ),
    }


def _check_export_freshness(
    zarr_path: Path, now: datetime
) -> dict:
    """Check export_timestamp in zarr attrs against SLO."""
    zattrs_path = zarr_path / ".zattrs"
    if not zattrs_path.exists():
        return {
            "export_timestamp": None,
            "export_age_hours": -1,
            "export_slo_met": False,
            "detail": f"No zarr store at {zarr_path}",
        }

    try:
        attrs = json.loads(zattrs_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return {
            "export_timestamp": None,
            "export_age_hours": -1,
            "export_slo_met": False,
            "detail": f"Cannot read .zattrs: {e}",
        }

    ts_str = attrs.get("export_timestamp")
    if not ts_str:
        return {
            "export_timestamp": None,
            "export_age_hours": -1,
            "export_slo_met": False,
            "detail": "export_timestamp missing from zarr attrs",
        }

    try:
        ts = datetime.fromisoformat(ts_str)
        age_hours = (now - ts).total_seconds() / 3600
    except (ValueError, TypeError):
        return {
            "export_timestamp": ts_str,
            "export_age_hours": -1,
            "export_slo_met": False,
            "detail": f"Cannot parse timestamp: {ts_str}",
        }

    slo_met = age_hours < FRESHNESS_SLO_HOURS
    age_str = (
        f"{age_hours:.0f}h ago"
        if age_hours < 48
        else f"{age_hours / 24:.0f}d ago"
    )
    return {
        "export_timestamp": ts_str,
        "export_age_hours": round(age_hours, 1),
        "export_slo_met": slo_met,
        "detail": (
            f"Exported {ts_str[:19]} ({age_str})"
            f" — SLO {FRESHNESS_SLO_HOURS}h: "
            f"{'MET' if slo_met else 'BREACHED'}"
        ),
    }


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
        result = _report_ledger(name, path, now)
        results.append(result)
        if result["status"] not in ("OK", "NO DATA"):
            any_issues = True

    # Export freshness check (ADR-018 SLO)
    zarr_path = args.data_dir / "assembled" / "grid.zarr"
    freshness = _check_export_freshness(zarr_path, now)
    if not freshness["export_slo_met"]:
        any_issues = True

    if args.json:
        import json as json_mod

        output = {
            "timestamp": now.isoformat(),
            "healthy": not any_issues,
            "freshness_slo_hours": FRESHNESS_SLO_HOURS,
            "export_age_hours": freshness["export_age_hours"],
            "export_slo_met": freshness["export_slo_met"],
            "sources": results,
        }
        print(json_mod.dumps(output, indent=2))
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
    print()

    for result in results:
        status = result["status"]
        name = result["name"]
        detail = result["detail"]

        if status == "OK":
            marker = "  "
        elif status == "NO DATA":
            marker = "? "
        else:
            marker = "! "

        print(f"{marker}[{status:7s}] {name:20s} {detail}")

    print()
    if any_issues:
        print("Issues detected. Check details above.")
        return 1
    print("All sources healthy. Export SLO met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
