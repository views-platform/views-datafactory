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

        status = "OK" if age_hours < 168 else "STALE"
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

    if args.json:
        import json as json_mod

        output = {
            "timestamp": now.isoformat(),
            "healthy": not any_issues,
            "sources": results,
        }
        print(json_mod.dumps(output, indent=2))
        return 1 if any_issues else 0

    print("=" * 60)
    print(f"DATAFACTORY HEALTH — {now.isoformat()[:19]}Z")
    print("=" * 60)
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
        print("Issues detected. Check ledger details.")
        return 1
    print("All sources healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
