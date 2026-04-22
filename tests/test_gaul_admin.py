"""Tests for datafactory_harvester.sources.gaul_admin."""

from __future__ import annotations

import io
import logging
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
            patch("datafactory_http.retry.requests.get") as mock_get,
            patch("datafactory_http.retry.time.sleep"),
        ):
            mock_get.side_effect = [
                _req.ConnectionError("transient"),
                mock_resp,
            ]
            result = _download_shapefile_zip(
                "http://example.com/test.zip",
                tmp_path / "cache",
                timeout=10,
            )

        assert mock_get.call_count == 2
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

        with patch("datafactory_http.retry.requests.get") as mock_get:
            result = _download_shapefile_zip(
                "http://example.com/test.zip",
                cache_dir,
            )

        mock_get.assert_not_called()
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

    _logger_name = "datafactory_harvester.sources.gaul_admin"

    def test_timeout_error_logged(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            caplog.at_level(logging.ERROR, logger=self._logger_name),
            pytest.raises(ValueError, match="timeout"),
        ):
            GaulAdminConfig(timeout=0)
        assert len(
            [r for r in caplog.records if r.levelno >= logging.ERROR]
        ) >= 1
