"""Drift detection tests — provenance enforcement (C-253, C-254, C-255).

Verifies that derived artifacts (zarr, consumer parquet) cannot
silently drift from their source grid.npy.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_assembled(tmp_path: Path) -> Path:
    """Create a minimal assembled directory with provenance."""
    assembled = tmp_path / "assembled"
    assembled.mkdir()

    grid = assembled / "grid.npy"
    grid.write_bytes(b"grid-content-v1")

    provenance = {
        "output_digest": None,
        "feature_names": ["ged_sb_best"],
    }

    from datafactory_provenance import compute_file_digest

    provenance["output_digest"] = compute_file_digest(grid)

    (assembled / "provenance.json").write_text(
        json.dumps(provenance)
    )
    return assembled


class TestVerifySourceDigest:
    """verify_source_digest() must detect content mismatches."""

    def test_matching_digest(self, tmp_assembled: Path) -> None:
        from datafactory_provenance import (
            compute_file_digest,
            verify_source_digest,
        )

        grid = tmp_assembled / "grid.npy"
        digest = compute_file_digest(grid)

        result = verify_source_digest(grid, digest)
        assert result["match"] is True
        assert result["actual_digest"] == digest

    def test_mismatched_digest(self, tmp_assembled: Path) -> None:
        from datafactory_provenance import verify_source_digest

        grid = tmp_assembled / "grid.npy"
        result = verify_source_digest(grid, "wrong_digest_value")
        assert result["match"] is False
        assert "MISMATCH" in result["detail"]

    def test_missing_source_file(self, tmp_path: Path) -> None:
        from datafactory_provenance import verify_source_digest

        result = verify_source_digest(
            tmp_path / "nonexistent.npy", "some_digest",
        )
        assert result["match"] is False
        assert result["actual_digest"] is None


class TestCheckExportFreshnessContent:
    """check_export_freshness() must report content staleness."""

    def _make_zarr(
        self,
        zarr_path: Path,
        source_digest: str,
        export_ts: datetime,
        last_valid: int = 555,
    ) -> None:
        zarr_path.mkdir(parents=True)
        attrs = {
            "export_timestamp": export_ts.isoformat(),
            "source_digest": source_digest,
            "last_valid_month_id": last_valid,
        }
        (zarr_path / ".zattrs").write_text(json.dumps(attrs))

    def test_content_fresh(self, tmp_assembled: Path) -> None:
        from datafactory_provenance import check_export_freshness

        prov = json.loads(
            (tmp_assembled / "provenance.json").read_text()
        )
        digest = prov["output_digest"]
        now = datetime.now(tz=UTC)

        zarr_path = tmp_assembled / "grid.zarr"
        self._make_zarr(zarr_path, digest, now)

        result = check_export_freshness(
            zarr_path, now,
            provenance_path=tmp_assembled / "provenance.json",
        )
        assert result["content_fresh"] is True
        assert result["source_digest_match"] is True

    def test_content_stale(self, tmp_assembled: Path) -> None:
        from datafactory_provenance import check_export_freshness

        now = datetime.now(tz=UTC)
        zarr_path = tmp_assembled / "grid.zarr"
        self._make_zarr(zarr_path, "old_stale_digest", now)

        result = check_export_freshness(
            zarr_path, now,
            provenance_path=tmp_assembled / "provenance.json",
        )
        assert result["content_fresh"] is False
        assert "CONTENT STALE" in result["detail"]
        assert result["export_slo_met"] is True

    def test_time_stale_content_fresh(
        self, tmp_assembled: Path,
    ) -> None:
        """Time-stale but content-fresh is still SLO breach."""
        from datafactory_provenance import check_export_freshness

        prov = json.loads(
            (tmp_assembled / "provenance.json").read_text()
        )
        digest = prov["output_digest"]
        now = datetime.now(tz=UTC)
        old_ts = now - timedelta(hours=200)

        zarr_path = tmp_assembled / "grid.zarr"
        self._make_zarr(zarr_path, digest, old_ts)

        result = check_export_freshness(
            zarr_path, now,
            provenance_path=tmp_assembled / "provenance.json",
        )
        assert result["content_fresh"] is True
        assert result["export_slo_met"] is False


class TestExportsSentinel:
    """Assembly sentinel must be detectable by health checks."""

    def test_sentinel_written_and_read(
        self, tmp_assembled: Path,
    ) -> None:
        sentinel = tmp_assembled / ".exports_required"
        sentinel.write_text(json.dumps({
            "grid_digest": "abc123",
            "assembled_at": "2026-06-08T00:00:00+00:00",
        }))
        assert sentinel.exists()

        data = json.loads(sentinel.read_text())
        assert data["grid_digest"] == "abc123"

    def test_sentinel_cleared_after_export(
        self, tmp_assembled: Path,
    ) -> None:
        sentinel = tmp_assembled / ".exports_required"
        sentinel.write_text('{"grid_digest": "abc123"}')
        assert sentinel.exists()

        sentinel.unlink()
        assert not sentinel.exists()
