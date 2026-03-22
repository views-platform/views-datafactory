"""Tests for PRIO-GRID static features harvester.

Tests use mocked API responses to avoid network dependency.
Follows Green/Beige/Red taxonomy (ADR-005).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow.parquet as pq
import pytest

from datafactory_harvester.sources.priogrid_static import (
    REQUIRED_CELL_FIELDS,
    PriogridStaticConfig,
    _discover_static_variables,
    _fetch_variable,
    fetch_priogrid_static,
)

# ---- Helpers ----


def _mock_variable_meta(
    name: str = "landarea",
) -> dict:
    """Create a mock variable metadata dict."""
    return {
        "id": 61,
        "name": name,
        "displayName": f"Test {name}",
        "category": "Land use",
        "type": "static",
        "unit": "km2",
        "sourceName": "Test source",
    }


def _mock_api_response(
    name: str = "landarea",
    n_cells: int = 5,
) -> dict:
    """Create a mock API data response."""
    cells = [
        {"gid": 49182 + i, "value": float(i + 1), "year": 0}
        for i in range(n_cells)
    ]
    return {
        "variable": _mock_variable_meta(name),
        "minValue": 1.0,
        "maxValue": float(n_cells),
        "availableYears": [],
        "cells": cells,
    }


def _mock_variables_response() -> list[dict]:
    """Create a mock /api/variables response."""
    return [
        {**_mock_variable_meta("landarea"), "type": "static"},
        {**_mock_variable_meta("mountains_mean"), "type": "static"},
        {**_mock_variable_meta("pop_gpw_sum"), "type": "yearly"},
    ]


# ---- Config: Green ----


class TestPriogridStaticConfigGreen:

    def test_defaults(self) -> None:
        cfg = PriogridStaticConfig()
        assert cfg.timeout == 60
        assert cfg.variables is None
        assert "priogrid_static" in str(cfg.data_dir)

    def test_custom_variables(self) -> None:
        cfg = PriogridStaticConfig(
            variables=("landarea", "mountains_mean")
        )
        assert cfg.variables == ("landarea", "mountains_mean")

    def test_frozen(self) -> None:
        cfg = PriogridStaticConfig()
        with pytest.raises(AttributeError):
            cfg.timeout = 120  # type: ignore[misc]


# ---- Config: Beige ----


class TestPriogridStaticConfigBeige:

    def test_timeout_too_low(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            PriogridStaticConfig(timeout=0)

    def test_timeout_negative(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            PriogridStaticConfig(timeout=-1)


# ---- Discovery: Green ----


class TestDiscoverVariablesGreen:

    def test_filters_to_static(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = (
            _mock_variables_response()
        )
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = _discover_static_variables(
                "https://example.com/api", timeout=10
            )

        assert len(result) == 2
        assert all(v["type"] == "static" for v in result)


# ---- Fetch Variable: Green ----


class TestFetchVariableGreen:

    def test_fetches_and_stores_parquet(
        self, tmp_path: Path
    ) -> None:
        config = PriogridStaticConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        variable = _mock_variable_meta("landarea")

        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_api_response(
            "landarea", n_cells=10
        )
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = _fetch_variable(config, variable)

        assert result["outcome"] == "success"
        assert result["n_cells"] == 10

        # Parquet created
        snap = tmp_path / "data" / "landarea.parquet"
        assert snap.exists()
        table = pq.read_table(snap)
        assert table.num_rows == 10
        assert set(table.column_names) == {"gid", "value"}

        # Provenance recorded
        assert (tmp_path / "ledger.jsonl").exists()
        entry = json.loads(
            (tmp_path / "ledger.jsonl")
            .read_text()
            .strip()
            .splitlines()[-1]
        )
        assert entry["outcome"] == "success"
        assert entry["n_cells"] == 10
        assert len(entry["content_digest"]) == 16

    def test_local_first_skip(self, tmp_path: Path) -> None:
        """Second fetch returns cached without API call."""
        config = PriogridStaticConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        variable = _mock_variable_meta("landarea")

        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_api_response(
            "landarea", n_cells=5
        )
        mock_resp.raise_for_status = MagicMock()

        # First fetch
        with patch("requests.get", return_value=mock_resp):
            r1 = _fetch_variable(config, variable)
        assert r1["outcome"] == "success"

        # Second fetch — should skip API
        r2 = _fetch_variable(config, variable)
        assert r2["outcome"] == "cached"


# ---- Fetch Variable: Red ----


class TestFetchVariableRed:

    def test_empty_cells_fails(self, tmp_path: Path) -> None:
        config = PriogridStaticConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        variable = _mock_variable_meta("empty_var")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "variable": variable,
            "cells": [],
            "minValue": 0,
            "maxValue": 0,
            "availableYears": [],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = _fetch_variable(config, variable)

        assert result["outcome"] == "failed"
        assert "0 cells" in result["errors"][0]

    def test_missing_required_field_fails(
        self, tmp_path: Path
    ) -> None:
        config = PriogridStaticConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        variable = _mock_variable_meta("bad_var")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "variable": variable,
            "cells": [{"gid": 1}],  # missing "value"
            "minValue": 0,
            "maxValue": 0,
            "availableYears": [],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = _fetch_variable(config, variable)

        assert result["outcome"] == "failed"
        assert "missing fields" in result["errors"][0]


# ---- Orchestrator: Green ----


class TestFetchPriogridStaticGreen:

    def test_fetches_all_static_variables(
        self, tmp_path: Path
    ) -> None:
        config = PriogridStaticConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        vars_resp = MagicMock()
        vars_resp.json.return_value = (
            _mock_variables_response()
        )
        vars_resp.raise_for_status = MagicMock()

        data_resp = MagicMock()
        data_resp.json.return_value = _mock_api_response(
            n_cells=3
        )
        data_resp.raise_for_status = MagicMock()

        with patch(
            "requests.get",
            side_effect=[vars_resp, data_resp, data_resp],
        ):
            results = fetch_priogrid_static(config)

        # Should fetch 2 static variables (not yearly)
        assert len(results) == 2
        assert all(
            r["outcome"] == "success" for r in results
        )


# ---- Registration: Green ----


class TestRegistrationGreen:

    def test_registered_in_source_registry(self) -> None:
        from datafactory_harvester.sources import (
            list_sources,
        )

        assert "priogrid_static" in list_sources()


# ---- Schema: Green ----


class TestSchemaGreen:

    def test_required_fields_declared(self) -> None:
        assert "gid" in REQUIRED_CELL_FIELDS
        assert "value" in REQUIRED_CELL_FIELDS
