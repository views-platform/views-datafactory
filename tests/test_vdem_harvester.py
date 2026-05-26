"""Tests for V-Dem harvester — CSV download and Parquet storage.

Green: happy path (config, download, caching, provenance, registry).
Beige: validation and boundary conditions.
Red: failure handling (network errors, corrupt downloads, missing columns).

Ref: ADR-035 (V-Dem source selection).
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

SAMPLE_VARIABLES = ("v2x_libdem", "v2xcl_dmove", "v2x_clphy")

SAMPLE_CSV = (
    "country_text_id,year,v2x_libdem,v2xcl_dmove,v2x_clphy,"
    "v2x_other\n"
    "NOR,2020,0.89,0.95,0.92,0.50\n"
    "SWE,2020,0.88,0.94,0.91,0.49\n"
    "NOR,2021,0.90,0.96,0.93,0.51\n"
    "SWE,2021,0.87,0.93,0.90,0.48\n"
)


def _make_vdem_zip(csv_content: str = SAMPLE_CSV) -> bytes:
    """Create a minimal in-memory ZIP containing a V-Dem CSV."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "V-Dem-CY-Full+Others-v16.csv",
            csv_content,
        )
    return buf.getvalue()


# ===================================================================
# GREEN — Config
# ===================================================================


class TestVdemConfigGreen:
    """Config defaults and immutability."""

    def test_defaults(self) -> None:
        from datafactory_harvester.sources.vdem import VdemConfig

        cfg = VdemConfig()
        assert len(cfg.variables) == 22
        assert cfg.version == "v16"
        assert cfg.data_dir == Path("data/raw/vdem")
        assert cfg.timeout > 0

    def test_frozen(self) -> None:
        from datafactory_harvester.sources.vdem import VdemConfig

        cfg = VdemConfig()
        with pytest.raises(AttributeError):
            cfg.timeout = 1  # type: ignore[misc]

    def test_custom_variables(self) -> None:
        from datafactory_harvester.sources.vdem import VdemConfig

        cfg = VdemConfig(variables=SAMPLE_VARIABLES)
        assert cfg.variables == SAMPLE_VARIABLES

    def test_output_path_includes_version(self) -> None:
        from datafactory_harvester.sources.vdem import VdemConfig

        cfg = VdemConfig(version="v16")
        assert "v16" in cfg.output_path.name
        assert cfg.output_path.suffix == ".parquet"


# ===================================================================
# GREEN — Download + provenance
# ===================================================================


class TestFetchVdemGreen:
    """Happy-path fetch."""

    def test_download_and_store(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        zip_data = _make_vdem_zip()
        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.vdem"
            ".request_with_retry",
            return_value=mock_resp,
        ):
            result = fetch_vdem(config)

        assert result["dataset"] == "vdem"
        assert result["outcome"] == "success"
        assert "content_digest" in result
        assert result["n_rows"] == 4
        assert config.output_path.exists()

        ledger = tmp_path / "ledger.jsonl"
        assert ledger.exists()
        entries = [
            json.loads(line)
            for line in ledger.read_text().strip().split("\n")
        ]
        assert entries[-1]["outcome"] == "success"
        assert entries[-1]["n_variables"] == 3

    def test_cache_hit_skips_download(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        zip_data = _make_vdem_zip()
        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.vdem"
            ".request_with_retry",
            return_value=mock_resp,
        ) as mock_req:
            fetch_vdem(config)
            result = fetch_vdem(config)

        assert result["outcome"] == "cached"
        assert mock_req.call_count == 1

    def test_force_refresh_re_downloads(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        zip_data = _make_vdem_zip()
        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.vdem"
            ".request_with_retry",
            return_value=mock_resp,
        ) as mock_req:
            fetch_vdem(config)
            result = fetch_vdem(config, force_refresh=True)

        assert result["outcome"] in ("success", "unchanged")
        assert mock_req.call_count == 2

    def test_parquet_contains_only_requested_columns(
        self, tmp_path: Path,
    ) -> None:
        import pyarrow.parquet as pq

        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        zip_data = _make_vdem_zip()
        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with patch(
            "datafactory_harvester.sources.vdem"
            ".request_with_retry",
            return_value=mock_resp,
        ):
            fetch_vdem(config)

        table = pq.read_table(config.output_path)
        col_names = set(table.column_names)

        assert "country_text_id" in col_names
        assert "year" in col_names
        for var in SAMPLE_VARIABLES:
            assert var in col_names
        assert "v2x_other" not in col_names


# ===================================================================
# BEIGE — Validation
# ===================================================================


class TestVdemConfigBeige:
    """Config validation."""

    def test_empty_variables_raises(self) -> None:
        from datafactory_harvester.sources.vdem import VdemConfig

        with pytest.raises(ValueError, match="variables"):
            VdemConfig(variables=())

    def test_invalid_timeout_raises(self) -> None:
        from datafactory_harvester.sources.vdem import VdemConfig

        with pytest.raises(ValueError, match="timeout"):
            VdemConfig(timeout=0)

    def test_empty_version_raises(self) -> None:
        from datafactory_harvester.sources.vdem import VdemConfig

        with pytest.raises(ValueError, match="version"):
            VdemConfig(version="")

    def test_duplicate_variables_raises(self) -> None:
        from datafactory_harvester.sources.vdem import VdemConfig

        with pytest.raises(ValueError, match="duplicate"):
            VdemConfig(
                variables=("v2x_libdem", "v2x_libdem"),
            )

    def test_empty_string_variable_raises(self) -> None:
        from datafactory_harvester.sources.vdem import VdemConfig

        with pytest.raises(ValueError, match="empty"):
            VdemConfig(variables=("v2x_libdem", ""))


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestFetchVdemRed:
    """Failure paths and outcome vocabulary."""

    def test_network_error_records_failure(
        self, tmp_path: Path,
    ) -> None:
        import requests

        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.vdem"
                ".request_with_retry",
                side_effect=requests.ConnectionError("timeout"),
            ),
            pytest.raises(requests.ConnectionError),
        ):
            fetch_vdem(config)

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
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        mock_resp = MagicMock()
        mock_resp.content = b"not a zip file"

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.vdem"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(zipfile.BadZipFile),
        ):
            fetch_vdem(config)

        entries = [
            json.loads(line)
            for line in (tmp_path / "ledger.jsonl")
            .read_text()
            .strip()
            .split("\n")
        ]
        assert entries[-1]["outcome"] == "failed"

    def test_missing_csv_in_zip_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "no csv here")
        zip_data = buf.getvalue()

        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.vdem"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(ValueError, match="No CSV"),
        ):
            fetch_vdem(config)

    def test_missing_column_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        csv_missing_col = (
            "country_text_id,year,v2x_libdem\n"
            "NOR,2020,0.89\n"
        )
        zip_data = _make_vdem_zip(csv_missing_col)
        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.vdem"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(ValueError, match="missing"),
        ):
            fetch_vdem(config)

    def test_parse_filter_failure_writes_ledger(
        self, tmp_path: Path,
    ) -> None:
        """C-207: _parse_and_filter failure must write a ledger entry."""
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        csv_missing_col = (
            "country_text_id,year,v2x_libdem\n"
            "NOR,2020,0.89\n"
        )
        zip_data = _make_vdem_zip(csv_missing_col)
        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.vdem"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(ValueError, match="missing"),
        ):
            fetch_vdem(config)

        ledger = (tmp_path / "ledger.jsonl").read_text().strip()
        assert ledger, "Ledger file is empty — no entry written"
        entry = json.loads(ledger.splitlines()[-1])
        assert entry["outcome"] == "failed", (
            f"Expected outcome='failed', got {entry['outcome']!r}"
        )

    def test_empty_csv_raises(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        csv_empty = (
            "country_text_id,year,v2x_libdem,"
            "v2xcl_dmove,v2x_clphy\n"
        )
        zip_data = _make_vdem_zip(csv_empty)
        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = VdemConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.vdem"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(ValueError, match="zero rows"),
        ):
            fetch_vdem(config)


# ===================================================================
# GREEN — Registry
# ===================================================================


class TestVdemRegistryGreen:
    """Source auto-registration."""

    def test_registered_in_source_registry(self) -> None:
        import datafactory_harvester.sources.vdem  # noqa: F401
        from datafactory_harvester.sources import list_sources

        assert "vdem" in list_sources()
