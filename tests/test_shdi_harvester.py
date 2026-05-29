"""Tests for SHDI harvester — GDL Data API download and Parquet storage.

Green: happy path (config, download, caching, provenance, crosswalk, registry).
Beige: validation and boundary conditions.
Red: failure handling (missing token, network errors, missing columns, zero rows).

Ref: ADR-036 (SHDI source selection).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow.parquet as pq
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_VARIABLES = ("shdi", "healthindex", "edindex")

SAMPLE_CSV = (
    "GDLCODE,level,country,region,year,"
    "shdi,healthindex,edindex,incindex\n"
    "NORr101,Subnat,Norway,Oslo,2020,"
    "0.95,0.97,0.96,0.92\n"
    "NORr102,Subnat,Norway,Bergen,2020,"
    "0.93,0.95,0.94,0.90\n"
    "NORr101,Subnat,Norway,Oslo,2021,"
    "0.96,0.97,0.97,0.93\n"
    "NORr102,Subnat,Norway,Bergen,2021,"
    "0.94,0.96,0.95,0.91\n"
    "NOR,National,Norway,,2020,"
    "0.94,0.96,0.95,0.91\n"
)

SAMPLE_CROSSWALK = [
    (100001, "NORr101"),
    (100002, "NORr101"),
    (100003, "NORr102"),
]

_SHDI_MODULE = "datafactory_harvester.sources.shdi"


def _mock_csv_response(
    csv_content: str = SAMPLE_CSV,
) -> MagicMock:
    """Create a mock response returning CSV bytes."""
    resp = MagicMock()
    resp.content = csv_content.encode()
    return resp


def _mock_shapefile_response() -> MagicMock:
    """Create a mock response returning dummy shapefile ZIP bytes."""
    resp = MagicMock()
    resp.content = b"fake-shapefile-zip"
    return resp


def _mock_build_crosswalk(
    shapefile_path: Path,
    centroid_path: Path,
) -> list[tuple[int, str]]:
    """Mock crosswalk builder returning fixed mapping."""
    return list(SAMPLE_CROSSWALK)


def _side_effect_for_download(csv_resp: MagicMock):
    """Return CSV response for first call, shapefile for second."""
    shp_resp = _mock_shapefile_response()
    responses = iter([csv_resp, shp_resp])
    return lambda *a, **kw: next(responses)


# ===================================================================
# GREEN — Config
# ===================================================================


class TestShdiConfigGreen:
    """Config defaults and immutability."""

    def test_defaults(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        cfg = ShdiConfig()
        assert len(cfg.variables) == 4
        assert cfg.version == "v10.2"
        assert cfg.data_dir == Path("data/raw/shdi")
        assert cfg.timeout > 0

    def test_frozen(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        cfg = ShdiConfig()
        with pytest.raises(AttributeError):
            cfg.version = "v9"  # type: ignore[misc]

    def test_custom_variables(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        cfg = ShdiConfig(variables=SAMPLE_VARIABLES)
        assert cfg.variables == SAMPLE_VARIABLES

    def test_output_path_includes_version(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        cfg = ShdiConfig(version="v10.2")
        assert "v10.2" in cfg.output_path.name
        assert cfg.output_path.suffix == ".parquet"

    def test_crosswalk_path(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        cfg = ShdiConfig()
        assert cfg.crosswalk_path.name == "gdl_to_pgid.parquet"

    def test_download_url_includes_indicators(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        cfg = ShdiConfig(variables=("shdi", "edindex"))
        assert "shdi+edindex" in cfg.download_url

    def test_shapefile_cache_path(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        cfg = ShdiConfig()
        assert cfg.shapefile_cache_path.parent == cfg.data_dir


# ===================================================================
# GREEN — Credential resolution
# ===================================================================


class TestGdlTokenGreen:
    """Token resolution (ADR-026)."""

    def test_token_from_argument(self) -> None:
        from datafactory_harvester.sources.shdi import get_gdl_token

        assert get_gdl_token("my-token") == "my-token"

    def test_token_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from datafactory_harvester.sources.shdi import get_gdl_token

        monkeypatch.setenv("GDL_API_TOKEN", "env-token")
        assert get_gdl_token() == "env-token"

    def test_argument_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from datafactory_harvester.sources.shdi import get_gdl_token

        monkeypatch.setenv("GDL_API_TOKEN", "env-token")
        assert get_gdl_token("arg-token") == "arg-token"

    def test_missing_token_raises(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from datafactory_harvester.sources.shdi import get_gdl_token

        monkeypatch.delenv("GDL_API_TOKEN", raising=False)
        with pytest.raises(ValueError, match="GDL_API_TOKEN"):
            get_gdl_token()


# ===================================================================
# GREEN — Download + provenance
# ===================================================================


class TestFetchShdiGreen:
    """Happy-path fetch."""

    def test_download_and_store(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        csv_resp = _mock_csv_response()

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                side_effect=_side_effect_for_download(csv_resp),
            ),
            patch(
                f"{_SHDI_MODULE}._build_crosswalk",
                side_effect=_mock_build_crosswalk,
            ),
        ):
            result = fetch_shdi(config)

        assert result["dataset"] == "shdi"
        assert result["outcome"] == "success"
        assert "content_digest" in result
        assert result["n_rows"] == 4
        assert result["n_regions"] == 2
        assert result["n_pgids_mapped"] == 3
        assert config.output_path.exists()
        assert config.crosswalk_path.exists()

        ledger = tmp_path / "ledger.jsonl"
        assert ledger.exists()
        entries = [
            json.loads(line)
            for line in ledger.read_text().strip().split("\n")
        ]
        assert entries[-1]["outcome"] == "success"
        assert entries[-1]["n_variables"] == 4
        assert entries[-1]["n_regions"] == 2

    def test_national_rows_filtered(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        csv_resp = _mock_csv_response()

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                side_effect=_side_effect_for_download(csv_resp),
            ),
            patch(
                f"{_SHDI_MODULE}._build_crosswalk",
                side_effect=_mock_build_crosswalk,
            ),
        ):
            result = fetch_shdi(config)

        table = pq.read_table(config.output_path)
        levels = set(table.column("level").to_pylist())
        assert levels == {"Subnat"}
        assert result["n_rows"] == 4

    def test_cache_hit_skips_download(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        call_count = 0

        def counting_side_effect(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                if call_count == 1:
                    return _mock_csv_response()
                return _mock_shapefile_response()
            raise AssertionError("Should not download again")

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                side_effect=counting_side_effect,
            ),
            patch(
                f"{_SHDI_MODULE}._build_crosswalk",
                side_effect=_mock_build_crosswalk,
            ),
        ):
            fetch_shdi(config)
            result = fetch_shdi(config)

        assert result["outcome"] == "cached"
        assert call_count == 2

    def test_force_refresh_re_downloads(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        csv_resp = _mock_csv_response()
        shp_resp = _mock_shapefile_response()

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                side_effect=[
                    csv_resp, shp_resp,
                    _mock_csv_response(), _mock_shapefile_response(),
                ],
            ) as mock_req,
            patch(
                f"{_SHDI_MODULE}._build_crosswalk",
                side_effect=_mock_build_crosswalk,
            ),
        ):
            fetch_shdi(config)
            result = fetch_shdi(config, force_refresh=True)

        assert result["outcome"] in ("success", "unchanged")
        assert mock_req.call_count == 4

    def test_parquet_contains_only_requested_columns(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        csv_resp = _mock_csv_response()

        config = ShdiConfig(
            variables=SAMPLE_VARIABLES,
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                side_effect=_side_effect_for_download(csv_resp),
            ),
            patch(
                f"{_SHDI_MODULE}._build_crosswalk",
                side_effect=_mock_build_crosswalk,
            ),
        ):
            fetch_shdi(config)

        table = pq.read_table(config.output_path)
        col_names = set(table.column_names)

        assert "GDLCODE" in col_names
        assert "year" in col_names
        for var in SAMPLE_VARIABLES:
            assert var in col_names
        assert "incindex" not in col_names

    def test_crosswalk_schema(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        csv_resp = _mock_csv_response()

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                side_effect=_side_effect_for_download(csv_resp),
            ),
            patch(
                f"{_SHDI_MODULE}._build_crosswalk",
                side_effect=_mock_build_crosswalk,
            ),
        ):
            fetch_shdi(config)

        table = pq.read_table(config.crosswalk_path)
        assert set(table.column_names) == {"gid", "gdl_code"}
        assert table.num_rows == 3
        assert table.schema.field("gid").type == "int32"
        assert table.schema.field("gdl_code").type == "string"

    def test_shapefile_cached_not_redownloaded(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        # Pre-cache the shapefile
        config.shapefile_cache_path.parent.mkdir(
            parents=True, exist_ok=True,
        )
        config.shapefile_cache_path.write_bytes(b"cached-zip")

        csv_resp = _mock_csv_response()

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                return_value=csv_resp,
            ) as mock_req,
            patch(
                f"{_SHDI_MODULE}._build_crosswalk",
                side_effect=_mock_build_crosswalk,
            ),
        ):
            fetch_shdi(config)

        assert mock_req.call_count == 1


# ===================================================================
# BEIGE — Validation
# ===================================================================


class TestShdiConfigBeige:
    """Config validation."""

    def test_empty_variables_raises(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        with pytest.raises(ValueError, match="variables"):
            ShdiConfig(variables=())

    def test_empty_version_raises(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        with pytest.raises(ValueError, match="version"):
            ShdiConfig(version="")

    def test_duplicate_variables_raises(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        with pytest.raises(ValueError, match="duplicate"):
            ShdiConfig(variables=("shdi", "shdi"))

    def test_empty_string_variable_raises(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        with pytest.raises(ValueError, match="empty"):
            ShdiConfig(variables=("shdi", ""))

    def test_invalid_timeout_raises(self) -> None:
        from datafactory_harvester.sources.shdi import ShdiConfig

        with pytest.raises(ValueError, match="timeout"):
            ShdiConfig(timeout=0)


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestFetchShdiRed:
    """Failure paths."""

    def test_missing_token_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        monkeypatch.delenv("GDL_API_TOKEN", raising=False)
        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with pytest.raises(ValueError, match="GDL_API_TOKEN"):
            fetch_shdi(config)

    def test_network_error_records_failure(
        self, tmp_path: Path,
    ) -> None:
        import requests

        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                side_effect=requests.ConnectionError("timeout"),
            ),
            pytest.raises(requests.ConnectionError),
        ):
            fetch_shdi(config)

        entries = [
            json.loads(line)
            for line in (tmp_path / "ledger.jsonl")
            .read_text()
            .strip()
            .split("\n")
        ]
        assert entries[-1]["outcome"] == "failed"

    def test_csv_missing_columns_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        bad_csv = "GDLCODE,year,shdi\nNORr101,2020,0.95\n"
        csv_resp = _mock_csv_response(bad_csv)

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                return_value=csv_resp,
            ),
            pytest.raises(ValueError, match="missing"),
        ):
            fetch_shdi(config)

    def test_parse_failure_writes_ledger(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        bad_csv = "GDLCODE,year,shdi\nNORr101,2020,0.95\n"
        csv_resp = _mock_csv_response(bad_csv)

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                return_value=csv_resp,
            ),
            pytest.raises(ValueError, match="missing"),
        ):
            fetch_shdi(config)

        ledger = (tmp_path / "ledger.jsonl").read_text().strip()
        assert ledger, "Ledger file is empty — no entry written"
        entry = json.loads(ledger.splitlines()[-1])
        assert entry["outcome"] == "failed"
        assert "missing" in entry["reason"].lower()

    def test_zero_rows_raises(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        empty_csv = (
            "GDLCODE,level,country,region,year,"
            "shdi,healthindex,edindex,incindex\n"
        )
        csv_resp = _mock_csv_response(empty_csv)

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                return_value=csv_resp,
            ),
            pytest.raises(ValueError, match="zero rows"),
        ):
            fetch_shdi(config)

        ledger = (tmp_path / "ledger.jsonl").read_text().strip()
        assert ledger
        entry = json.loads(ledger.splitlines()[-1])
        assert entry["outcome"] == "failed"

    def test_only_national_rows_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        national_only = (
            "GDLCODE,level,country,region,year,"
            "shdi,healthindex,edindex,incindex\n"
            "NOR,National,Norway,,2020,"
            "0.94,0.96,0.95,0.91\n"
        )
        csv_resp = _mock_csv_response(national_only)

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                return_value=csv_resp,
            ),
            pytest.raises(ValueError, match="subnational"),
        ):
            fetch_shdi(config)

        ledger = (tmp_path / "ledger.jsonl").read_text().strip()
        entry = json.loads(ledger.splitlines()[-1])
        assert entry["outcome"] == "failed"

    def test_shapefile_download_failure_records_ledger(
        self, tmp_path: Path,
    ) -> None:
        import requests

        from datafactory_harvester.sources.shdi import (
            ShdiConfig,
            fetch_shdi,
        )

        csv_resp = _mock_csv_response()

        config = ShdiConfig(
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        def csv_then_fail(*a, **kw):
            if not hasattr(csv_then_fail, "called"):
                csv_then_fail.called = True
                return csv_resp
            raise requests.ConnectionError("CDN down")

        with (
            patch(
                f"{_SHDI_MODULE}.get_gdl_token",
                return_value="test-token",
            ),
            patch(
                f"{_SHDI_MODULE}.request_with_retry",
                side_effect=csv_then_fail,
            ),
            pytest.raises(requests.ConnectionError),
        ):
            fetch_shdi(config)

        ledger = (tmp_path / "ledger.jsonl").read_text().strip()
        assert ledger, "Ledger file is empty — no entry written"
        entry = json.loads(ledger.splitlines()[-1])
        assert entry["outcome"] == "failed"
        assert "shapefile" in entry["reason"].lower()


# ===================================================================
# GREEN — Registry
# ===================================================================


class TestShdiRegistryGreen:
    """Source auto-registration."""

    def test_registered_in_source_registry(self) -> None:
        import datafactory_harvester.sources.shdi  # noqa: F401
        from datafactory_harvester.sources import list_sources

        assert "shdi" in list_sources()
