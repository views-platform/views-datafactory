"""Tests for PRIO-GRID shapefile harvester — outcome vocabulary + failure recording.

Green: happy path (download, extraction, provenance, outcome field).
Beige: unchanged content detection.
Red: failure handling (extraction error records failure in ledger).

Ref: ADR-032 (harvest idempotence), C-186.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_fake_shapefile_zip() -> bytes:
    """Create a minimal in-memory ZIP containing fake .shp/.shx/.dbf files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("priogrid.shp", b"fake shapefile")
        zf.writestr("priogrid.shx", b"fake index")
        zf.writestr("priogrid.dbf", b"fake attributes")
    return buf.getvalue()


# ===================================================================
# GREEN — Download + provenance
# ===================================================================


class TestFetchShapefileGreen:
    """Happy-path fetch: download, extract, record provenance."""

    def test_fetch_records_success_on_normal_download(
        self, tmp_path: Path,
    ) -> None:
        """First download records outcome='success' in ledger."""
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
            fetch_shapefile,
        )

        cfg = ShapefileHarvesterConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        mock_resp = MagicMock()
        mock_resp.content = _make_fake_shapefile_zip()

        with (
            patch(
                "datafactory_priogrid.shapefile_harvester"
                ".request_with_retry",
                return_value=mock_resp,
            ),
        ):
            result = fetch_shapefile(cfg)

        assert result == cfg.data_dir / "shapefile"
        assert (result / "priogrid.shp").exists()

        entries = [
            json.loads(line)
            for line in cfg.ledger_path.read_text().strip().split("\n")
        ]
        assert len(entries) == 1
        assert entries[0]["outcome"] == "success"
        assert entries[0]["dataset"] == "priogrid_shapefile"
        assert "content_digest" in entries[0]
        assert "extracted_files" in entries[0]

    def test_ledger_entry_includes_outcome_field(
        self, tmp_path: Path,
    ) -> None:
        """Every ledger entry has an 'outcome' field."""
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
            fetch_shapefile,
        )

        cfg = ShapefileHarvesterConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        mock_resp = MagicMock()
        mock_resp.content = _make_fake_shapefile_zip()

        with patch(
            "datafactory_priogrid.shapefile_harvester"
            ".request_with_retry",
            return_value=mock_resp,
        ):
            fetch_shapefile(cfg)

        entries = [
            json.loads(line)
            for line in cfg.ledger_path.read_text().strip().split("\n")
        ]
        for entry in entries:
            assert "outcome" in entry

    def test_success_entry_retains_changed_field(
        self, tmp_path: Path,
    ) -> None:
        """Backward compat: success entries still have 'changed' field."""
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
            fetch_shapefile,
        )

        cfg = ShapefileHarvesterConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        mock_resp = MagicMock()
        mock_resp.content = _make_fake_shapefile_zip()

        with patch(
            "datafactory_priogrid.shapefile_harvester"
            ".request_with_retry",
            return_value=mock_resp,
        ):
            fetch_shapefile(cfg)

        entry = json.loads(
            cfg.ledger_path.read_text().strip().split("\n")[-1]
        )
        assert "changed" in entry
        assert entry["changed"] is True


# ===================================================================
# BEIGE — Unchanged content
# ===================================================================


class TestFetchShapefileBeige:
    """Unchanged content detection."""

    def test_fetch_records_unchanged_when_digest_matches(
        self, tmp_path: Path,
    ) -> None:
        """Second download with same content records outcome='unchanged'."""
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
            fetch_shapefile,
        )

        cfg = ShapefileHarvesterConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        zip_bytes = _make_fake_shapefile_zip()
        mock_resp = MagicMock()
        mock_resp.content = zip_bytes

        with patch(
            "datafactory_priogrid.shapefile_harvester"
            ".request_with_retry",
            return_value=mock_resp,
        ):
            fetch_shapefile(cfg)
            fetch_shapefile(cfg, force_refresh=True)

        entries = [
            json.loads(line)
            for line in cfg.ledger_path.read_text().strip().split("\n")
        ]
        assert len(entries) == 2
        assert entries[0]["outcome"] == "success"
        assert entries[1]["outcome"] == "unchanged"
        assert entries[1]["changed"] is False


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestFetchShapefileRed:
    """Failure paths — fail loud with provenance (ADR-011)."""

    def test_fetch_records_failed_on_extraction_error(
        self, tmp_path: Path,
    ) -> None:
        """Extraction failure records outcome='failed' before re-raising."""
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
            fetch_shapefile,
        )

        cfg = ShapefileHarvesterConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        mock_resp = MagicMock()
        mock_resp.content = b"not a zip file"

        with (
            patch(
                "datafactory_priogrid.shapefile_harvester"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(zipfile.BadZipFile),
        ):
            fetch_shapefile(cfg)

        assert cfg.ledger_path.exists()
        entry = json.loads(
            cfg.ledger_path.read_text().strip().split("\n")[-1]
        )
        assert entry["outcome"] == "failed"
        assert entry["dataset"] == "priogrid_shapefile"

    def test_failed_entry_retains_changed_false(
        self, tmp_path: Path,
    ) -> None:
        """Failed entries have changed=False for backward compat."""
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
            fetch_shapefile,
        )

        cfg = ShapefileHarvesterConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        mock_resp = MagicMock()
        mock_resp.content = b"corrupt zip"

        with (
            patch(
                "datafactory_priogrid.shapefile_harvester"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(zipfile.BadZipFile),
        ):
            fetch_shapefile(cfg)

        entry = json.loads(
            cfg.ledger_path.read_text().strip().split("\n")[-1]
        )
        assert entry["changed"] is False
