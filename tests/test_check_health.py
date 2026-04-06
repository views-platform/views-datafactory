"""Tests for datafactory_provenance.health — resolves C-60.

Covers the three core functions that assess pipeline health:
read_last_entries, report_ledger, and check_export_freshness.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from datafactory_provenance.health import (
    check_export_freshness,
    read_last_entries,
    report_ledger,
)

# ── Helpers ──────────────────────────────────────────────


def _write_ledger(path: Path, entries: list[dict]) -> None:
    """Write a list of dicts as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e) for e in entries]
    path.write_text("\n".join(lines) + "\n")


def _make_entry(
    ts: str,
    outcome: str = "success",
    version: str = "25.1",
) -> dict:
    return {
        "timestamp": ts,
        "outcome": outcome,
        "version": version,
        "content_digest": "abc123",
    }


NOW = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)
RECENT_TS = "2026-04-06T12:00:00+00:00"  # 24h ago
STALE_TS = "2026-03-20T12:00:00+00:00"  # 18 days ago


# ── read_last_entries ────────────────────────────────────


class TestReadLastEntries:

    def test_reads_last_n(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        entries = [{"i": i} for i in range(10)]
        _write_ledger(ledger, entries)
        result = read_last_entries(ledger, n=3)
        assert len(result) == 3
        # Last entries first (reversed order)
        assert result[0]["i"] == 9
        assert result[2]["i"] == 7

    def test_empty_file(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text("")
        assert read_last_entries(ledger) == []

    def test_missing_file(self, tmp_path: Path) -> None:
        ledger = tmp_path / "nonexistent.jsonl"
        assert read_last_entries(ledger) == []

    def test_corrupt_lines_skipped(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text(
            '{"a": 1}\n'
            "NOT JSON\n"
            '{"b": 2}\n'
        )
        result = read_last_entries(ledger, n=5)
        assert len(result) == 2
        assert result[0]["b"] == 2
        assert result[1]["a"] == 1

    def test_blank_lines_skipped(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text('{"a": 1}\n\n\n{"b": 2}\n\n')
        result = read_last_entries(ledger, n=5)
        assert len(result) == 2


# ── report_ledger ────────────────────────────────────────


class TestReportLedger:

    def test_ok_for_recent_success(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry(RECENT_TS)])
        result = report_ledger("test", ledger, NOW)
        assert result["status"] == "OK"
        assert result["name"] == "test"

    def test_stale_for_old_success(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry(STALE_TS)])
        result = report_ledger("test", ledger, NOW)
        assert result["status"] == "STALE"

    def test_no_data_for_missing_ledger(self, tmp_path: Path) -> None:
        ledger = tmp_path / "missing.jsonl"
        result = report_ledger("test", ledger, NOW)
        assert result["status"] == "NO DATA"

    def test_failing_when_all_failed(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        entries = [
            _make_entry(RECENT_TS, outcome="failed")
            for _ in range(5)
        ]
        _write_ledger(ledger, entries)
        result = report_ledger("test", ledger, NOW)
        assert result["status"] == "FAILING"

    def test_ok_when_no_outcome_field(self, tmp_path: Path) -> None:
        """Entries without outcome (consolidation/viewpoint) are successes."""
        ledger = tmp_path / "ledger.jsonl"
        entry = {"timestamp": RECENT_TS, "content_digest": "abc"}
        _write_ledger(ledger, [entry])
        result = report_ledger("test", ledger, NOW)
        assert result["status"] == "OK"

    def test_recent_failures_counted(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        entries = [
            _make_entry(RECENT_TS, outcome="success"),
            _make_entry(RECENT_TS, outcome="failed"),
            _make_entry(RECENT_TS, outcome="failed"),
        ]
        _write_ledger(ledger, entries)
        result = report_ledger("test", ledger, NOW)
        assert result["status"] == "OK"
        assert "2 recent failures" in result["detail"]

    def test_version_and_digest_returned(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry(RECENT_TS, version="25.1")])
        result = report_ledger("test", ledger, NOW)
        assert result["version"] == "25.1"
        assert result["digest"] == "abc123"


# ── check_export_freshness ───────────────────────────────


class TestCheckExportFreshness:

    def test_slo_met(self, tmp_path: Path) -> None:
        zarr = tmp_path / "grid.zarr"
        zarr.mkdir()
        (zarr / ".zattrs").write_text(
            json.dumps({"export_timestamp": RECENT_TS})
        )
        result = check_export_freshness(zarr, NOW)
        assert result["export_slo_met"] is True
        assert result["export_age_hours"] > 0

    def test_slo_breached(self, tmp_path: Path) -> None:
        zarr = tmp_path / "grid.zarr"
        zarr.mkdir()
        (zarr / ".zattrs").write_text(
            json.dumps({"export_timestamp": STALE_TS})
        )
        result = check_export_freshness(zarr, NOW)
        assert result["export_slo_met"] is False

    def test_missing_zarr(self, tmp_path: Path) -> None:
        zarr = tmp_path / "nonexistent.zarr"
        result = check_export_freshness(zarr, NOW)
        assert result["export_slo_met"] is False
        assert result["export_age_hours"] == -1

    def test_missing_timestamp_field(self, tmp_path: Path) -> None:
        zarr = tmp_path / "grid.zarr"
        zarr.mkdir()
        (zarr / ".zattrs").write_text(json.dumps({"crs": "EPSG:4326"}))
        result = check_export_freshness(zarr, NOW)
        assert result["export_slo_met"] is False
        assert "missing" in result["detail"]

    def test_corrupt_zattrs(self, tmp_path: Path) -> None:
        zarr = tmp_path / "grid.zarr"
        zarr.mkdir()
        (zarr / ".zattrs").write_text("NOT JSON")
        result = check_export_freshness(zarr, NOW)
        assert result["export_slo_met"] is False
        assert result["export_age_hours"] == -1
