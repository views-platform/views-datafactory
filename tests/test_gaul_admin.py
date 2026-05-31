"""Tests for datafactory_harvester.sources.gaul_admin."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from datafactory_harvester.sources.gaul_admin import GaulAdminConfig


def _make_fake_shp_zip() -> bytes:
    """Create a minimal in-memory ZIP with a fake .shp file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("test.shp", "fake shapefile")
        zf.writestr("test.dbf", "fake dbf")
    return buf.getvalue()


class TestDownloadShapefileZip:

    def test_retries_on_transient_failure(self, tmp_path: Path) -> None:
        """_download_shapefile_zip uses request_with_retry (C-82)."""
        from datafactory_harvester.sources.gaul_admin import (
            _download_shapefile_zip,
        )

        fake_zip = _make_fake_shp_zip()
        mock_resp = MagicMock()
        mock_resp.content = fake_zip

        import requests as _req

        with (
            patch("datafactory_http.retry.requests.request") as mock_request,
            patch("datafactory_http.retry.time.sleep"),
        ):
            mock_request.side_effect = [
                _req.ConnectionError("transient"),
                mock_resp,
            ]
            result = _download_shapefile_zip(
                "http://example.com/test.zip",
                tmp_path / "cache",
                timeout=10,
            )

        assert mock_request.call_count == 2
        assert result.suffix == ".shp"
        assert result.exists()

    def test_skips_download_when_cached(self, tmp_path: Path) -> None:
        """When .shp already exists, skip download."""
        from datafactory_harvester.sources.gaul_admin import (
            _download_shapefile_zip,
        )

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "test.shp").write_text("cached")

        with patch("datafactory_http.retry.requests.request") as mock_request:
            result = _download_shapefile_zip(
                "http://example.com/test.zip",
                cache_dir,
            )

        mock_request.assert_not_called()
        assert result.name == "test.shp"


# ---- GaulAdminConfig Green ----


class TestGaulAdminConfigGreen:

    def test_defaults(self) -> None:
        cfg = GaulAdminConfig()
        assert cfg.timeout == 300
        assert cfg.variables is None
        assert "gaul_admin" in str(cfg.data_dir)

    def test_frozen(self) -> None:
        cfg = GaulAdminConfig()
        with pytest.raises(AttributeError):
            cfg.timeout = 1  # type: ignore[misc]

    def test_custom_variables(self) -> None:
        cfg = GaulAdminConfig(variables=("gaul0_code",))
        assert cfg.variables == ("gaul0_code",)


# ---- GaulAdminConfig Beige ----


class TestGaulAdminConfigBeige:

    def test_rejects_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            GaulAdminConfig(timeout=0)

    def test_rejects_negative_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            GaulAdminConfig(timeout=-5)


# ---- GaulAdminConfig Red ----


class TestGaulAdminConfigRed:

    def test_mutation_rejected(self) -> None:
        cfg = GaulAdminConfig()
        with pytest.raises(AttributeError):
            cfg.variables = ("gaul0_code",)  # type: ignore[misc]


# ---- ADR-008 compliance ----


class TestGaulAdminADR008:

    def test_timeout_error_raised(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            GaulAdminConfig(timeout=0)


# ---- C-188: failure path writes ledger entry ----

_GAUL_MODULE = "datafactory_harvester.sources.gaul_admin"


class TestGaulAdminFailureLedger:

    def test_write_variable_failure_records_ledger_entry(
        self, tmp_path: Path,
    ) -> None:
        """When _write_variable raises, a 'failed' entry must
        appear in the provenance ledger (C-188)."""
        ledger = tmp_path / "ledger.jsonl"
        config = GaulAdminConfig(
            data_dir=tmp_path / "data",
            cache_dir=tmp_path / "cache",
            ledger_path=ledger,
            variables=("gaul0_code",),
        )

        with (
            patch(f"{_GAUL_MODULE}._download_shapefile_zip") as mock_dl,
            patch(f"{_GAUL_MODULE}._load_centroids") as mock_cen,
            patch(f"{_GAUL_MODULE}._spatial_join") as mock_sj,
            patch(f"{_GAUL_MODULE}._write_variable") as mock_wv,
        ):
            mock_dl.return_value = tmp_path / "fake.shp"
            mock_cen.return_value = []
            mock_sj.return_value = {}
            mock_wv.side_effect = RuntimeError("disk full")

            from datafactory_harvester.sources.gaul_admin import (
                fetch_gaul_admin,
            )

            results = fetch_gaul_admin(config, force_refresh=True)

        assert results[0]["outcome"] == "failed"

        entries = [
            json.loads(line)
            for line in ledger.read_text().splitlines()
            if line.strip()
        ]
        failed = [e for e in entries if e.get("outcome") == "failed"]
        assert len(failed) == 1, (
            f"Expected 1 failed ledger entry, got {len(failed)}"
        )
        assert failed[0]["version"] == "gaul0_code"
        assert failed[0]["dataset"] == "gaul_admin"
        assert "disk full" in failed[0]["errors"][0]
