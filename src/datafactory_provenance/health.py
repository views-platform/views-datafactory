"""Health diagnostics — ledger freshness and SLO evaluation.

Read-only functions that assess pipeline health by inspecting
provenance ledgers and export metadata. Used by check_health.py
and available for programmatic monitoring.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

__all__ = [
    "FRESHNESS_SLO_HOURS",
    "check_export_freshness",
    "read_last_entries",
    "report_ledger",
]

# Freshness SLO: maximum acceptable age of exported data (ADR-018).
# Monthly pipeline runs on the 21st. 7 days (168h) allows one missed
# cycle before data is flagged as stale.
FRESHNESS_SLO_HOURS = 168


def _format_age(age_hours: float) -> str:
    if age_hours < 48:
        return f"{age_hours:.0f}h ago"
    return f"{age_hours / 24:.0f}d ago"


def read_last_entries(
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


def report_ledger(
    name: str, ledger_path: Path, now: datetime
) -> dict:
    """Report health for one ledger."""
    entries = read_last_entries(ledger_path, n=10)

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
            age_str = _format_age(age_hours)
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


def check_export_freshness(
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
    age_str = _format_age(age_hours)

    # Data boundary: last month with real UCDP observations.
    # UCDP releases around the 20th with data for the prior month,
    # so expected minimum is (current_month - 2) to allow lag.
    last_valid = attrs.get("last_valid_month_id")
    expected_min = (now.year - 1980) * 12 + now.month - 2
    data_boundary_current: bool | None = None
    if last_valid is not None:
        last_valid = int(last_valid)
        data_boundary_current = last_valid >= expected_min

    detail = (
        f"Exported {ts_str[:19]} ({age_str})"
        f" — SLO {FRESHNESS_SLO_HOURS}h: "
        f"{'MET' if slo_met else 'BREACHED'}"
    )

    result: dict = {
        "export_timestamp": ts_str,
        "export_age_hours": round(age_hours, 1),
        "export_slo_met": slo_met,
        "last_valid_month_id": last_valid,
        "data_boundary_current": data_boundary_current,
        "detail": detail,
    }
    return result
