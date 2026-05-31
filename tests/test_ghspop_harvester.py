"""Tests for GHS-POP harvester — GeoTIFF download from JRC.

Green: happy path (config, download, caching, provenance, registry).
Beige: validation and boundary conditions.
Red: failure handling (network errors, corrupt downloads).

Ref: ADR-029 (GHS-POP source selection), ADR-030 (tifffile tooling).
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


class TestGhsPopConfigGreen:
    """Config defaults and immutability."""

    def test_defaults(self) -> None:
        from datafactory_harvester.sources.ghspop import GhsPopConfig

        cfg = GhsPopConfig()
        assert cfg.epochs == KNOWN_EPOCHS
        assert cfg.resolution == "30ss"
        assert cfg.crs == "4326"
        assert cfg.release == "R2023A"
        assert cfg.data_dir == Path("data/raw/ghspop")
        assert cfg.ledger_path == Path("provenance/ghspop/ingestion_ledger.jsonl")
        assert cfg.timeout > 0

    def test_frozen(self) -> None:
        from datafactory_harvester.sources.ghspop import GhsPopConfig

        cfg = GhsPopConfig()
        with pytest.raises(AttributeError):
            cfg.timeout = 1  # type: ignore[misc]

    def test_custom_epochs(self) -> None:
        from datafactory_harvester.sources.ghspop import GhsPopConfig

        cfg = GhsPopConfig(epochs=(2020,))
        assert cfg.epochs == (2020,)

    def test_builds_download_url(self) -> None:
        from datafactory_harvester.sources.ghspop import GhsPopConfig

        cfg = GhsPopConfig()
        url = cfg.download_url(2020)
        assert "GHS_POP_E2020_GLOBE_R2023A_4326_30ss" in url
        assert url.endswith(".zip")

    def test_builds_tif_filename(self) -> None:
        from datafactory_harvester.sources.ghspop import GhsPopConfig

        cfg = GhsPopConfig()
        name = cfg.tif_filename(2020)
        assert name == "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"


# ===================================================================
# GREEN — Download + provenance
# ===================================================================


class TestFetchGhsPopGreen:
    """Happy-path fetch for a single epoch."""

    def test_download_single_epoch(self, tmp_path: Path) -> None:
        """Fetching one epoch downloads ZIP, extracts TIF, records provenance."""
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        tif_name = cfg.tif_filename(2020)
        fake_zip = _make_fake_geotiff_zip(tif_name)

        mock_resp = MagicMock()
        mock_resp.content = fake_zip

        with (
            patch("datafactory_http.retry.requests.request", return_value=mock_resp),
            patch("datafactory_http.retry.time.sleep"),
        ):
            results = fetch_ghspop(cfg)

        assert len(results) == 1
        r = results[0]
        assert r["outcome"] == "success"
        assert r["epoch"] == 2020
        assert r["dataset"] == "ghspop"
        assert "content_digest" in r

        # TIF extracted to data_dir with correct content
        tif_path = cfg.data_dir / tif_name
        assert tif_path.exists()
        assert tif_path.read_bytes() == b"fake geotiff data"

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        """Ledger entry written after successful download."""
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        tif_name = cfg.tif_filename(2020)
        fake_zip = _make_fake_geotiff_zip(tif_name)

        mock_resp = MagicMock()
        mock_resp.content = fake_zip

        with (
            patch("datafactory_http.retry.requests.request", return_value=mock_resp),
            patch("datafactory_http.retry.time.sleep"),
        ):
            fetch_ghspop(cfg)

        ledger_lines = cfg.ledger_path.read_text().strip().split("\n")
        assert len(ledger_lines) >= 1
        entry = json.loads(ledger_lines[-1])
        assert entry["dataset"] == "ghspop"
        assert entry["outcome"] == "success"
        assert "content_digest" in entry
        assert "timestamp" in entry

        # Digest matches the extracted TIF content
        from datafactory_provenance import compute_content_digest

        expected_digest = compute_content_digest(b"fake geotiff data")
        assert entry["content_digest"] == expected_digest

    def test_skips_cached_epoch(self, tmp_path: Path) -> None:
        """When TIF exists and ledger has a digest, skip download."""
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        # Pre-populate: TIF exists + ledger has entry
        tif_path = cfg.data_dir / cfg.tif_filename(2020)
        tif_path.parent.mkdir(parents=True, exist_ok=True)
        tif_path.write_bytes(b"cached geotiff")

        from datafactory_provenance import (
            append_ledger_entry,
            compute_content_digest,
        )

        digest = compute_content_digest(b"cached geotiff")
        append_ledger_entry(cfg.ledger_path, {
            "dataset": "ghspop",
            "version": "E2020",
            "content_digest": digest,
            "outcome": "success",
        })

        with patch("datafactory_http.retry.requests.request") as mock_req:
            results = fetch_ghspop(cfg)

        mock_req.assert_not_called()
        assert len(results) == 1
        assert results[0]["outcome"] == "cached"

    def test_uncached_when_digest_mismatch(self, tmp_path: Path) -> None:
        """File with mismatched digest triggers re-download."""
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        # Pre-populate with stale/corrupt content
        tif_path = cfg.data_dir / cfg.tif_filename(2020)
        tif_path.parent.mkdir(parents=True, exist_ok=True)
        tif_path.write_bytes(b"corrupt geotiff")

        from datafactory_provenance import append_ledger_entry

        append_ledger_entry(cfg.ledger_path, {
            "dataset": "ghspop",
            "version": "E2020",
            "content_digest": "wrong_digest_value",
            "outcome": "success",
        })

        # Should re-download because digest doesn't match
        tif_name = cfg.tif_filename(2020)
        fake_zip = _make_fake_geotiff_zip(tif_name)
        mock_resp = MagicMock()
        mock_resp.content = fake_zip

        with (
            patch("datafactory_http.retry.requests.request", return_value=mock_resp),
            patch("datafactory_http.retry.time.sleep"),
        ):
            results = fetch_ghspop(cfg)

        assert results[0]["outcome"] == "success"
        assert tif_path.read_bytes() == b"fake geotiff data"

    def test_multiple_epochs(self, tmp_path: Path) -> None:
        """Fetching multiple epochs returns one result per epoch."""
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(1975, 2020),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        def make_response(method: str, url: str, **kwargs: object) -> MagicMock:
            # Extract epoch from URL to build correct filename
            for epoch in (1975, 2020):
                if f"E{epoch}" in url:
                    tif_name = cfg.tif_filename(epoch)
                    resp = MagicMock()
                    resp.content = _make_fake_geotiff_zip(tif_name)
                    return resp
            raise ValueError(f"unexpected URL: {url}")

        with (
            patch("datafactory_http.retry.requests.request", side_effect=make_response),
            patch("datafactory_http.retry.time.sleep"),
        ):
            results = fetch_ghspop(cfg)

        assert len(results) == 2
        epochs_fetched = {r["epoch"] for r in results}
        assert epochs_fetched == {1975, 2020}


# ===================================================================
# GREEN — Registry
# ===================================================================


class TestGhsPopRegistryGreen:
    """Source registration."""

    def test_registered_in_sources(self) -> None:
        import datafactory_harvester.sources.ghspop  # noqa: F401
        from datafactory_harvester.sources import list_sources

        assert "ghspop" in list_sources()


# ===================================================================
# BEIGE — Validation
# ===================================================================


class TestGhsPopConfigBeige:
    """Config validation — boundary conditions."""

    def test_rejects_unknown_epoch(self) -> None:
        from datafactory_harvester.sources.ghspop import GhsPopConfig

        with pytest.raises(ValueError, match="epoch"):
            GhsPopConfig(epochs=(1999,))

    def test_rejects_zero_timeout(self) -> None:
        from datafactory_harvester.sources.ghspop import GhsPopConfig

        with pytest.raises(ValueError, match="timeout"):
            GhsPopConfig(timeout=0)

    def test_rejects_negative_timeout(self) -> None:
        from datafactory_harvester.sources.ghspop import GhsPopConfig

        with pytest.raises(ValueError, match="timeout"):
            GhsPopConfig(timeout=-5)

    def test_empty_epochs_accepted(self) -> None:
        """Empty epochs tuple is valid — fetch returns empty list."""
        from datafactory_harvester.sources.ghspop import GhsPopConfig

        cfg = GhsPopConfig(epochs=())
        assert cfg.epochs == ()


class TestFetchGhsPopBeige:
    """Fetch boundary conditions."""

    def test_force_refresh_overrides_cache(self, tmp_path: Path) -> None:
        """force_refresh=True re-downloads even if cached."""
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        # Pre-populate cache
        tif_path = cfg.data_dir / cfg.tif_filename(2020)
        tif_path.parent.mkdir(parents=True, exist_ok=True)
        tif_path.write_bytes(b"old geotiff")

        from datafactory_provenance import append_ledger_entry, compute_content_digest

        append_ledger_entry(cfg.ledger_path, {
            "dataset": "ghspop",
            "version": "E2020",
            "content_digest": compute_content_digest(b"old geotiff"),
            "outcome": "success",
        })

        tif_name = cfg.tif_filename(2020)
        fake_zip = _make_fake_geotiff_zip(tif_name)
        mock_resp = MagicMock()
        mock_resp.content = fake_zip

        with (
            patch("datafactory_http.retry.requests.request", return_value=mock_resp),
            patch("datafactory_http.retry.time.sleep"),
        ):
            results = fetch_ghspop(cfg, force_refresh=True)

        assert results[0]["outcome"] == "success"


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestFetchGhsPopRed:
    """Failure modes — fail loud (ADR-011)."""

    def test_network_failure_records_ledger(self, tmp_path: Path) -> None:
        """Network failure records a ledger entry with outcome='failed'."""
        import requests as _req

        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=_req.ConnectionError("network down"),
            ),
            patch("datafactory_http.retry.time.sleep"),
            pytest.raises(_req.ConnectionError),
        ):
            fetch_ghspop(cfg)

        # Ledger should still have a failure entry
        assert cfg.ledger_path.exists()
        entry = json.loads(cfg.ledger_path.read_text().strip().split("\n")[-1])
        assert entry["outcome"] == "failed"

    def test_corrupt_zip_raises_and_records_ledger(self, tmp_path: Path) -> None:
        """Non-ZIP content raises and records failure in ledger."""
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        mock_resp = MagicMock()
        mock_resp.content = b"this is not a zip file"

        with (
            patch("datafactory_http.retry.requests.request", return_value=mock_resp),
            patch("datafactory_http.retry.time.sleep"),
            pytest.raises(zipfile.BadZipFile),
        ):
            fetch_ghspop(cfg)

        assert cfg.ledger_path.exists()
        entry = json.loads(cfg.ledger_path.read_text().strip().split("\n")[-1])
        assert entry["outcome"] == "failed"

    def test_zip_with_no_tif_raises(self, tmp_path: Path) -> None:
        """Valid ZIP containing no expected TIF raises ValueError."""
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("README.txt", "no geotiff here")
        mock_resp = MagicMock()
        mock_resp.content = buf.getvalue()

        with (
            patch("datafactory_http.retry.requests.request", return_value=mock_resp),
            patch("datafactory_http.retry.time.sleep"),
            pytest.raises(ValueError, match="Expected.*in ZIP"),
        ):
            fetch_ghspop(cfg)

        entry = json.loads(
            cfg.ledger_path.read_text().strip().split("\n")[-1]
        )
        assert entry["outcome"] == "failed"
        assert "reason" in entry

    def test_zip_with_wrong_tif_name_raises(self, tmp_path: Path) -> None:
        """ZIP with a TIF under unexpected name raises ValueError (ADR-011)."""
        from datafactory_harvester.sources.ghspop import (
            GhsPopConfig,
            fetch_ghspop,
        )

        cfg = GhsPopConfig(
            epochs=(2020,),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("some_other_file.tif", b"raster data")
        mock_resp = MagicMock()
        mock_resp.content = buf.getvalue()

        with (
            patch("datafactory_http.retry.requests.request", return_value=mock_resp),
            patch("datafactory_http.retry.time.sleep"),
            pytest.raises(ValueError, match="JRC naming"),
        ):
            fetch_ghspop(cfg)

        entry = json.loads(
            cfg.ledger_path.read_text().strip().split("\n")[-1]
        )
        assert entry["outcome"] == "failed"
        assert "Expected" in entry["reason"]
