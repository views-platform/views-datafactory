"""Tests for datafactory_provenance.health — resolves C-60.

Covers the three core functions that assess pipeline health:
read_last_entries, report_ledger, and check_export_freshness.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from datafactory_provenance.health import (
    FRESHNESS_SLO_HOURS,
    SOURCE_SLO,
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


NOW = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
RECENT_TS = (NOW - timedelta(hours=24)).isoformat()
STALE_TS = (NOW - timedelta(hours=FRESHNESS_SLO_HOURS + 32)).isoformat()


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


# ── Per-source SLO (report_ledger with slo_hours) ────────


class TestPerSourceSLO:

    def test_static_source_never_stale(self, tmp_path: Path) -> None:
        """slo_hours=None means the source is static — always OK."""
        very_old_ts = (NOW - timedelta(days=365)).isoformat()
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry(very_old_ts)])
        result = report_ledger("PRIO-GRID Static", ledger, NOW, slo_hours=None)
        assert result["status"] == "OK"
        assert result["slo"] == "static"

    def test_yearly_source_ok_within_window(self, tmp_path: Path) -> None:
        """UCDP Annual with 8760h SLO: 6 months old is OK."""
        six_months_ago = (NOW - timedelta(days=180)).isoformat()
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry(six_months_ago)])
        result = report_ledger("UCDP Annual", ledger, NOW, slo_hours=8760)
        assert result["status"] == "OK"
        assert result["slo"] == "1y"

    def test_yearly_source_stale_beyond_window(self, tmp_path: Path) -> None:
        """UCDP Annual with 8760h SLO: 400 days old is STALE."""
        old_ts = (NOW - timedelta(days=400)).isoformat()
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry(old_ts)])
        result = report_ledger("UCDP Annual", ledger, NOW, slo_hours=8760)
        assert result["status"] == "STALE"

    def test_monthly_source_ok_within_window(self, tmp_path: Path) -> None:
        """UCDP Candidate with 744h SLO: 20 days old is OK."""
        twenty_days = (NOW - timedelta(days=20)).isoformat()
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry(twenty_days)])
        result = report_ledger("UCDP Candidate", ledger, NOW, slo_hours=744)
        assert result["status"] == "OK"
        assert result["slo"] == "31d"

    def test_monthly_source_stale_beyond_window(self, tmp_path: Path) -> None:
        """UCDP Candidate with 744h SLO: 35 days old is STALE."""
        old_ts = (NOW - timedelta(days=35)).isoformat()
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry(old_ts)])
        result = report_ledger("UCDP Candidate", ledger, NOW, slo_hours=744)
        assert result["status"] == "STALE"

    def test_default_slo_backwards_compatible(self, tmp_path: Path) -> None:
        """Without slo_hours, uses FRESHNESS_SLO_HOURS (168h)."""
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry(STALE_TS)])
        result = report_ledger("test", ledger, NOW)
        assert result["status"] == "STALE"

    def test_unparseable_timestamp_is_stale(self, tmp_path: Path) -> None:
        """Corrupt timestamp must not silently pass as OK."""
        ledger = tmp_path / "ledger.jsonl"
        _write_ledger(ledger, [_make_entry("not-a-date")])
        result = report_ledger("test", ledger, NOW, slo_hours=744)
        assert result["status"] == "STALE"

    def test_source_slo_dict_matches_registry(self) -> None:
        """SOURCE_SLO is derived from PIPELINE_SOURCES."""
        from datafactory_provenance.source_registry import (
            PIPELINE_SOURCES,
        )
        expected = {s.name for s in PIPELINE_SOURCES}
        assert expected == set(SOURCE_SLO.keys())

    def test_static_sources_have_none_slo(self) -> None:
        assert SOURCE_SLO["PRIO-GRID Static"] is None
        assert SOURCE_SLO["PRIO-GRID Shapefile"] is None

    def test_slo_label_in_no_data_result(self, tmp_path: Path) -> None:
        """Missing ledger still reports the SLO label."""
        ledger = tmp_path / "nonexistent.jsonl"
        result = report_ledger("test", ledger, NOW, slo_hours=None)
        assert result["slo"] == "static"

    def test_slo_label_in_failing_result(self, tmp_path: Path) -> None:
        """All-failed ledger still reports the SLO label."""
        ledger = tmp_path / "ledger.jsonl"
        entries = [_make_entry(RECENT_TS, outcome="failed") for _ in range(5)]
        _write_ledger(ledger, entries)
        result = report_ledger("test", ledger, NOW, slo_hours=744)
        assert result["slo"] == "31d"


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

    def test_data_boundary_current(self, tmp_path: Path) -> None:
        """last_valid_month_id present and recent."""
        zarr = tmp_path / "grid.zarr"
        zarr.mkdir()
        expected_min = (NOW.year - 1980) * 12 + NOW.month - 2
        (zarr / ".zattrs").write_text(json.dumps({
            "export_timestamp": RECENT_TS,
            "last_valid_month_id": expected_min,
        }))
        result = check_export_freshness(zarr, NOW)
        assert result["data_boundary_current"] is True
        assert result["last_valid_month_id"] == expected_min

    def test_data_boundary_stale(self, tmp_path: Path) -> None:
        """last_valid_month_id present but too old."""
        zarr = tmp_path / "grid.zarr"
        zarr.mkdir()
        expected_min = (NOW.year - 1980) * 12 + NOW.month - 2
        (zarr / ".zattrs").write_text(json.dumps({
            "export_timestamp": RECENT_TS,
            "last_valid_month_id": expected_min - 3,
        }))
        result = check_export_freshness(zarr, NOW)
        assert result["data_boundary_current"] is False


# ── Red tests: check_export_freshness ───────────────────


class TestCheckExportFreshnessRed:

    def test_corrupted_zattrs_json(self, tmp_path: Path) -> None:
        zarr = tmp_path / "grid.zarr"
        zarr.mkdir()
        (zarr / ".zattrs").write_text("{truncated")
        result = check_export_freshness(zarr, NOW)
        assert result["export_slo_met"] is False
        assert result["export_age_hours"] == -1

    def test_missing_export_timestamp(self, tmp_path: Path) -> None:
        zarr = tmp_path / "grid.zarr"
        zarr.mkdir()
        (zarr / ".zattrs").write_text(json.dumps({
            "last_valid_month_id": 540,
        }))
        result = check_export_freshness(zarr, NOW)
        assert result["export_slo_met"] is False
        assert "missing" in result["detail"]

    def test_unparseable_timestamp(self, tmp_path: Path) -> None:
        zarr = tmp_path / "grid.zarr"
        zarr.mkdir()
        (zarr / ".zattrs").write_text(json.dumps({
            "export_timestamp": "not-a-date",
        }))
        result = check_export_freshness(zarr, NOW)
        assert result["export_slo_met"] is False
        assert "Cannot parse" in result["detail"]


# ── Red tests: report_ledger ────────────────────────────


class TestReportLedgerRed:

    def test_corrupted_ledger_line(self, tmp_path: Path) -> None:
        """Mixed valid + invalid JSON lines should not crash."""
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text(
            "NOT JSON AT ALL\n"
            + json.dumps(_make_entry(RECENT_TS)) + "\n"
        )
        result = report_ledger("test", ledger, NOW)
        assert result["status"] == "OK"

    def test_empty_ledger_file(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text("")
        result = report_ledger("test", ledger, NOW)
        assert result["status"] == "NO DATA"

    def test_binary_garbage_in_ledger(self, tmp_path: Path) -> None:
        """Binary garbage crashes read_text — documents C-136."""
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_bytes(b"\x80\x81\x82\n")
        with pytest.raises(UnicodeDecodeError):
            report_ledger("test", ledger, NOW)
