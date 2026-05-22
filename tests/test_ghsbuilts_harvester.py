"""Tests for GHS-BUILT-S harvester — GeoTIFF download from JRC.

Green: happy path (config, download, caching, provenance, registry).
Beige: validation and boundary conditions.
Red: failure handling (network errors, corrupt downloads).

Ref: ADR-034 (GHS-BUILT-S source selection), ADR-030 (tifffile tooling).
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_geotiff_zip(filename: str = "test.tif") -> bytes:
    """Create a minimal in-memory ZIP containing a fake .tif file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, b"fake geotiff data")
    return buf.getvalue()


KNOWN_EPOCHS = (
    1975, 1980, 1985, 1990, 1995,
    2000, 2005, 2010, 2015, 2020, 2025, 2030,
)


# ===================================================================
# GREEN — Config
# ===================================================================


class TestGhsBuiltSConfigGreen:
    """Config defaults and immutability."""

    def test_defaults(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        assert cfg.epochs == KNOWN_EPOCHS
        assert cfg.resolution == "30ss"
        assert cfg.crs == "4326"
        assert cfg.release == "R2023A"
        assert cfg.data_dir == Path("data/raw/ghsbuilts")
        assert cfg.ledger_path == Path(
            "provenance/ghsbuilts/ingestion_ledger.jsonl"
        )
        assert cfg.timeout > 0

    def test_frozen(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        with pytest.raises(AttributeError):
            cfg.timeout = 1  # type: ignore[misc]

    def test_custom_epochs(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig(epochs=(2020,))
        assert cfg.epochs == (2020,)

    def test_builds_download_url(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        url = cfg.download_url(2020)
        assert "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss" in url
        assert url.endswith(".zip")

    def test_builds_tif_filename(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        name = cfg.tif_filename(2020)
        assert name == (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )


# ===================================================================
# GREEN — Download + provenance
# ===================================================================


class TestFetchGhsBuiltSGreen:
    """Happy-path fetch for a single epoch."""

    def test_download_single_epoch(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        zip_data = _make_fake_geotiff_zip(tif_name)

        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = GhsBuiltSConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            return_value=mock_resp,
        ):
            results = fetch_ghsbuilts(config)

        assert len(results) == 1
        r = results[0]
        assert r["dataset"] == "ghsbuilts"
        assert r["epoch"] == 2020
        assert r["outcome"] == "success"
        assert "content_digest" in r

        tif_path = tmp_path / "raw" / tif_name
        assert tif_path.exists()

        ledger = tmp_path / "ledger.jsonl"
        assert ledger.exists()
        entries = [
            json.loads(line)
            for line in ledger.read_text().strip().split("\n")
        ]
        assert len(entries) == 1
        assert entries[0]["outcome"] == "success"
        assert entries[0]["dataset"] == "ghsbuilts"
        assert entries[0]["version"] == "E2020"

    def test_cache_hit_skips_download(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        zip_data = _make_fake_geotiff_zip(tif_name)

        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = GhsBuiltSConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            return_value=mock_resp,
        ) as mock_req:
            fetch_ghsbuilts(config)
            results = fetch_ghsbuilts(config)

        assert results[0]["outcome"] == "cached"
        assert mock_req.call_count == 1

    def test_force_refresh_re_downloads(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        zip_data = _make_fake_geotiff_zip(tif_name)

        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = GhsBuiltSConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            return_value=mock_resp,
        ) as mock_req:
            fetch_ghsbuilts(config)
            results = fetch_ghsbuilts(
                config, force_refresh=True,
            )

        assert results[0]["outcome"] == "success"
        assert mock_req.call_count == 2


# ===================================================================
# BEIGE — Validation
# ===================================================================


class TestGhsBuiltSConfigBeige:
    """Config validation."""

    def test_unknown_epoch_raises(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        with pytest.raises(ValueError, match="Unknown epoch"):
            GhsBuiltSConfig(epochs=(1999,))

    def test_invalid_timeout_raises(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        with pytest.raises(ValueError, match="timeout"):
            GhsBuiltSConfig(timeout=0)


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestFetchGhsBuiltSRed:
    """Failure paths and outcome vocabulary."""

    def test_network_error_records_failure(
        self, tmp_path: Path,
    ) -> None:
        import requests

        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        config = GhsBuiltSConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.ghsbuilts"
                ".request_with_retry",
                side_effect=requests.ConnectionError("timeout"),
            ),
            pytest.raises(requests.ConnectionError),
        ):
            fetch_ghsbuilts(config)

        entries = [
            json.loads(line)
            for line in (tmp_path / "ledger.jsonl")
            .read_text()
            .strip()
            .split("\n")
        ]
        assert entries[-1]["outcome"] == "failed"

    def test_bad_zip_records_failure(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        mock_resp = MagicMock()
        mock_resp.content = b"not a zip file"

        config = GhsBuiltSConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.ghsbuilts"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(zipfile.BadZipFile),
        ):
            fetch_ghsbuilts(config)

        entries = [
            json.loads(line)
            for line in (tmp_path / "ledger.jsonl")
            .read_text()
            .strip()
            .split("\n")
        ]
        assert entries[-1]["outcome"] == "failed"

    def test_missing_tif_in_zip_records_failure(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        zip_data = _make_fake_geotiff_zip("wrong_name.tif")
        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = GhsBuiltSConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.ghsbuilts"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(ValueError, match="Expected"),
        ):
            fetch_ghsbuilts(config)

        entries = [
            json.loads(line)
            for line in (tmp_path / "ledger.jsonl")
            .read_text()
            .strip()
            .split("\n")
        ]
        assert entries[-1]["outcome"] == "failed"


# ===================================================================
# GREEN — Registry
# ===================================================================


class TestGhsBuiltSRegistryGreen:
    """Source auto-registration."""

    def test_registered_in_source_registry(self) -> None:
        import datafactory_harvester.sources.ghsbuilts  # noqa: F401
        from datafactory_harvester.sources import list_sources

        assert "ghsbuilts" in list_sources()

    def test_source_entry_in_pipeline_sources(self) -> None:
        from datafactory_provenance.source_registry import (
            PIPELINE_SOURCES,
        )

        names = [s.name for s in PIPELINE_SOURCES]
        assert "GHS-BUILT-S" in names
        assert "GHS-BUILT-S Viewpoint" in names
        assert "GHS-BUILT-S Compilation" in names

    def test_feature_in_registry(self) -> None:
        from datafactory_provenance.source_registry import (
            get_all_features,
        )

        features = get_all_features()
        assert "ghsbuilts_built_area" in features
