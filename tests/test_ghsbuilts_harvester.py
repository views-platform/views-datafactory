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

    def test_uncached_when_digest_mismatch(
        self, tmp_path: Path,
    ) -> None:
        """File with mismatched digest triggers re-download."""
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )

        config = GhsBuiltSConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        # Pre-populate with stale/corrupt content
        tif_path = config.data_dir / tif_name
        tif_path.parent.mkdir(parents=True, exist_ok=True)
        tif_path.write_bytes(b"corrupt geotiff")

        from datafactory_provenance import append_ledger_entry

        append_ledger_entry(config.ledger_path, {
            "dataset": "ghsbuilts",
            "version": "E2020",
            "content_digest": "wrong_digest_value",
            "outcome": "success",
        })

        # Should re-download because digest doesn't match
        zip_data = _make_fake_geotiff_zip(tif_name)
        mock_resp = MagicMock()
        mock_resp.content = zip_data

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            return_value=mock_resp,
        ):
            results = fetch_ghsbuilts(config)

        assert results[0]["outcome"] == "success"
        assert tif_path.read_bytes() == b"fake geotiff data"

    def test_multi_epoch_download(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_2020 = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        tif_2025 = (
            "GHS_BUILT_S_E2025_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )

        def _side_effect(url, **kwargs):
            resp = MagicMock()
            if "E2020" in url:
                resp.content = _make_fake_geotiff_zip(tif_2020)
            else:
                resp.content = _make_fake_geotiff_zip(tif_2025)
            return resp

        config = GhsBuiltSConfig(
            epochs=(2020, 2025),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            side_effect=_side_effect,
        ):
            results = fetch_ghsbuilts(config)

        assert len(results) == 2
        assert all(r["outcome"] == "success" for r in results)
        assert (tmp_path / "raw" / tif_2020).exists()
        assert (tmp_path / "raw" / tif_2025).exists()

    def test_url_structure_matches_jrc(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
        )

        cfg = GhsBuiltSConfig()
        url = cfg.download_url(2020)

        assert "jrc" in url.lower() or "jeodpp" in url.lower()
        assert "GHS_BUILT_S" in url
        assert "E2020" in url
        assert "R2023A" in url
        assert "4326" in url
        assert "30ss" in url

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
# GREEN — Config details (#284, C-189)
# ===================================================================


class TestGhsBuiltSConfigDetailsGreen:
    """Per-epoch URL and filename generation."""

    def test_each_epoch_url_unique(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        urls = [cfg.download_url(e) for e in KNOWN_EPOCHS]
        assert len(urls) == len(set(urls))

    def test_each_epoch_tif_unique(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        names = [cfg.tif_filename(e) for e in KNOWN_EPOCHS]
        assert len(names) == len(set(names))

    def test_url_contains_epoch_year(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        for epoch in KNOWN_EPOCHS:
            assert f"E{epoch}" in cfg.download_url(epoch)

    def test_tif_contains_epoch_year(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        for epoch in KNOWN_EPOCHS:
            assert f"E{epoch}" in cfg.tif_filename(epoch)

    def test_url_ends_with_zip(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        for epoch in KNOWN_EPOCHS:
            assert cfg.download_url(epoch).endswith(".zip")

    def test_tif_ends_with_tif(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        for epoch in KNOWN_EPOCHS:
            assert cfg.tif_filename(epoch).endswith(".tif")

    def test_release_in_url(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        assert cfg.release in cfg.download_url(2020)

    def test_crs_in_url(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        assert cfg.crs in cfg.download_url(2020)

    def test_resolution_in_url(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        assert cfg.resolution in cfg.download_url(2020)

    def test_known_epochs_constant_matches_config(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            KNOWN_EPOCHS as SRC_KNOWN_EPOCHS,
        )
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
        )

        cfg = GhsBuiltSConfig()
        assert cfg.epochs == SRC_KNOWN_EPOCHS
        assert cfg.epochs == KNOWN_EPOCHS

    def test_dataset_id_is_ghsbuilts(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import DATASET_ID

        assert DATASET_ID == "ghsbuilts"


# ===================================================================
# GREEN — Fetch result structure (#284, C-189)
# ===================================================================


class TestFetchResultStructureGreen:
    """Result dict structure for each outcome."""

    def test_success_result_has_required_keys(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        mock_resp = MagicMock()
        mock_resp.content = _make_fake_geotiff_zip(tif_name)

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

        r = results[0]
        assert "dataset" in r
        assert "epoch" in r
        assert "outcome" in r
        assert "content_digest" in r

    def test_cached_result_has_digest(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        mock_resp = MagicMock()
        mock_resp.content = _make_fake_geotiff_zip(tif_name)

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
            fetch_ghsbuilts(config)
            results = fetch_ghsbuilts(config)

        r = results[0]
        assert r["outcome"] == "cached"
        assert "content_digest" in r
        assert len(r["content_digest"]) == 16

    def test_data_dir_created_if_absent(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        mock_resp = MagicMock()
        mock_resp.content = _make_fake_geotiff_zip(tif_name)

        deep_dir = tmp_path / "a" / "b" / "c"
        config = GhsBuiltSConfig(
            epochs=(2020,),
            data_dir=deep_dir,
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            return_value=mock_resp,
        ):
            fetch_ghsbuilts(config)

        assert deep_dir.exists()

    def test_provenance_entry_has_version(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        mock_resp = MagicMock()
        mock_resp.content = _make_fake_geotiff_zip(tif_name)

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
            fetch_ghsbuilts(config)

        entry = json.loads(
            (tmp_path / "ledger.jsonl").read_text().strip()
        )
        assert entry["version"] == "E2020"
        assert entry["epoch"] == 2020

    def test_provenance_has_size_and_digest(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        mock_resp = MagicMock()
        mock_resp.content = _make_fake_geotiff_zip(tif_name)

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
            fetch_ghsbuilts(config)

        entry = json.loads(
            (tmp_path / "ledger.jsonl").read_text().strip()
        )
        assert "size_bytes" in entry
        assert "content_digest" in entry
        assert entry["size_bytes"] > 0

    def test_default_config_not_none(self, tmp_path: Path) -> None:

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            side_effect=Exception("should not reach"),
        ), patch(
            "datafactory_harvester.sources.ghsbuilts.GhsBuiltSConfig"
            ".data_dir",
            new_callable=lambda: property(lambda _: tmp_path),
        ):
            pass
        # Just verify None config creates a default
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig
        cfg = GhsBuiltSConfig()
        assert cfg is not None


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

    def test_empty_epochs_raises(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        with pytest.raises(ValueError, match="epoch"):
            GhsBuiltSConfig(epochs=())

    def test_custom_data_dir(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig(
            data_dir=Path("/custom/path"),
        )
        assert cfg.data_dir == Path("/custom/path")

    def test_negative_timeout_raises(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        with pytest.raises(ValueError, match="timeout"):
            GhsBuiltSConfig(timeout=-1)

    def test_single_epoch_accepted(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig(epochs=(1975,))
        assert cfg.epochs == (1975,)

    def test_first_known_epoch_accepted(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig(epochs=(1975,))
        assert 1975 in cfg.epochs

    def test_last_known_epoch_accepted(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig(epochs=(2030,))
        assert 2030 in cfg.epochs

    def test_custom_ledger_path(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig(
            ledger_path=Path("/custom/ledger.jsonl"),
        )
        assert cfg.ledger_path == Path("/custom/ledger.jsonl")


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


class TestGhsBuiltSConfigRed:
    """Config adversarial: mutation, type abuse."""

    def test_config_mutation_rejected(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        with pytest.raises(AttributeError):
            cfg.epochs = (2020,)  # type: ignore[misc]

    def test_config_mutation_data_dir_rejected(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        cfg = GhsBuiltSConfig()
        with pytest.raises(AttributeError):
            cfg.data_dir = Path("/evil")  # type: ignore[misc]

    def test_multiple_unknown_epochs_raises(self) -> None:
        from datafactory_harvester.sources.ghsbuilts import GhsBuiltSConfig

        with pytest.raises(ValueError, match="Unknown epoch"):
            GhsBuiltSConfig(epochs=(1999, 2001))


class TestFetchEpochIsolationRed:
    """Failure isolation: one epoch's failure doesn't corrupt another."""

    def test_first_epoch_failure_preserves_second(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            _fetch_epoch,
        )

        tif_2025 = (
            "GHS_BUILT_S_E2025_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )

        config = GhsBuiltSConfig(
            epochs=(2020, 2025),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        bad_resp = MagicMock()
        bad_resp.content = b"not a zip"

        good_resp = MagicMock()
        good_resp.content = _make_fake_geotiff_zip(tif_2025)

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            return_value=bad_resp,
        ), pytest.raises(zipfile.BadZipFile):
            _fetch_epoch(config, 2020, False)

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            return_value=good_resp,
        ):
            result = _fetch_epoch(config, 2025, False)

        assert result["outcome"] == "success"
        assert result["epoch"] == 2025


# ===================================================================
# GREEN — Registry
# ===================================================================


# ===================================================================
# GREEN — Provenance details (#284, C-189)
# ===================================================================


class TestHarvesterProvenanceDetailsGreen:
    """Provenance ledger entry structure and content."""

    def test_provenance_has_ledger_version(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        mock_resp = MagicMock()
        mock_resp.content = _make_fake_geotiff_zip(tif_name)

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
            fetch_ghsbuilts(config)

        entry = json.loads(
            (tmp_path / "ledger.jsonl").read_text().strip()
        )
        assert "ledger_version" in entry
        assert "digest_algorithm" in entry
        assert entry["ledger_version"] >= 1
        assert "sha256" in entry["digest_algorithm"]

    def test_provenance_digest_is_16_hex(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_name = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        mock_resp = MagicMock()
        mock_resp.content = _make_fake_geotiff_zip(tif_name)

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
            fetch_ghsbuilts(config)

        entry = json.loads(
            (tmp_path / "ledger.jsonl").read_text().strip()
        )
        digest = entry["content_digest"]
        assert len(digest) == 16
        assert all(c in "0123456789abcdef" for c in digest)

    def test_multi_epoch_provenance_entries(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ghsbuilts import (
            GhsBuiltSConfig,
            fetch_ghsbuilts,
        )

        tif_2020 = (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )
        tif_2025 = (
            "GHS_BUILT_S_E2025_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )

        def _side_effect(url, **kwargs):
            resp = MagicMock()
            if "E2020" in url:
                resp.content = _make_fake_geotiff_zip(tif_2020)
            else:
                resp.content = _make_fake_geotiff_zip(tif_2025)
            return resp

        config = GhsBuiltSConfig(
            epochs=(2020, 2025),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.ghsbuilts"
            ".request_with_retry",
            side_effect=_side_effect,
        ):
            fetch_ghsbuilts(config)

        lines = (tmp_path / "ledger.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
        e1 = json.loads(lines[0])
        e2 = json.loads(lines[1])
        assert e1["version"] == "E2020"
        assert e2["version"] == "E2025"
        assert e1["outcome"] == "success"
        assert e2["outcome"] == "success"


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
