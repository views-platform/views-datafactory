"""Tests for UCDP Annual source — mock-based, no network.

Tests the config validation, API client retry, and full
fetch_ucdp_annual orchestration flow.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from datafactory_harvester.sources.ucdp_annual import (
    UcdpAnnualConfig,
    fetch_ucdp_annual,
)

# ---- Config Validation ----


class TestUcdpAnnualConfigGreen:

    def test_defaults(self) -> None:
        cfg = UcdpAnnualConfig()
        assert cfg.version == "25.1"
        assert cfg.start_year == 1989
        assert cfg.end_year == 2024

    def test_frozen(self) -> None:
        cfg = UcdpAnnualConfig()
        with pytest.raises(AttributeError):
            cfg.version = "26.1"  # type: ignore[misc]


class TestUcdpAnnualConfigBeige:

    def test_rejects_end_before_start(self) -> None:
        with pytest.raises(ValueError, match="end_year"):
            UcdpAnnualConfig(start_year=2025, end_year=2024)

    def test_rejects_zero_page_size(self) -> None:
        with pytest.raises(ValueError, match="page_size"):
            UcdpAnnualConfig(page_size=0)

    def test_rejects_zero_retries(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            UcdpAnnualConfig(max_retries=0)

    def test_rejects_empty_version(self) -> None:
        with pytest.raises(ValueError, match="version"):
            UcdpAnnualConfig(version="")


# ---- Mock API Helpers ----


def _make_api_response(events: list[dict]) -> dict:
    """Create a valid UCDP API response envelope."""
    return {
        "TotalCount": len(events),
        "TotalPages": 1,
        "Result": events,
    }


def _make_events(n: int = 3) -> list[dict]:
    """Create minimal valid UCDP events."""
    return [
        {
            "id": i,
            "country_id": 100 + i,
            "country": f"Country{i}",
            "date_start": f"2024-01-{i + 1:02d}",
            "best": i * 10,
            "high": i * 15,
            "low": i * 5,
            "type_of_violence": 1,
            "event_clarity": 1,
            "code_status": "Clear",
            "where_prec": 1,
            "date_prec": 1,
            "number_of_sources": 2,
        }
        for i in range(1, n + 1)
    ]


# ---- Full Flow (Mock) ----


class TestFetchUcdpAnnualGreen:

    def test_full_flow(self, tmp_path: Path) -> None:
        """Mock API: fetch -> validate -> store -> provenance."""
        events = _make_events(5)
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_api_response(events)
        mock_resp.raise_for_status = MagicMock()

        config = UcdpAnnualConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "provenance" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.get",
                return_value=mock_resp,
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test-token"}),
        ):
            result = fetch_ucdp_annual(config)

        assert result.exists()
        assert result.suffix == ".parquet"

        # Provenance recorded
        ledger = config.ledger_path
        assert ledger.exists()
        entry = json.loads(ledger.read_text().strip().splitlines()[-1])
        assert entry["dataset"] == "ucdp_annual"
        assert entry["outcome"] == "success"
        assert "content_digest" in entry

    def test_skips_when_snapshot_exists(self, tmp_path: Path) -> None:
        """When snapshot and ledger exist, skip fetch."""
        config = UcdpAnnualConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "provenance" / "ledger.jsonl",
        )

        # Pre-create snapshot and ledger
        name = (
            f"ucdp_ged_v{config.version}"
            f"_{config.start_year}_{config.end_year}.parquet"
        )
        snap_path = config.data_dir / name
        snap_path.parent.mkdir(parents=True)
        snap_path.write_text("fake")

        from datafactory_provenance import append_ledger_entry

        append_ledger_entry(config.ledger_path, {"content_digest": "abc123"})

        with patch(
            "datafactory_http.retry.requests.get"
        ) as mock_get:
            result = fetch_ucdp_annual(config)

        mock_get.assert_not_called()
        assert result == snap_path


class TestFetchUcdpAnnualBeige:

    def test_validation_failure_records_ledger(self, tmp_path: Path) -> None:
        """When validation fails, a failed ledger entry is still recorded."""
        # Events missing required fields
        bad_events = [{"id": 1}]
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_api_response(bad_events)
        mock_resp.raise_for_status = MagicMock()

        config = UcdpAnnualConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "provenance" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.get",
                return_value=mock_resp,
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test-token"}),
            pytest.raises(ValueError, match="Validation failed"),
        ):
            fetch_ucdp_annual(config)

        # Failed attempt still recorded in ledger
        assert config.ledger_path.exists()
        entry = json.loads(
            config.ledger_path.read_text().strip().splitlines()[-1]
        )
        assert entry["outcome"] == "failed"


# ---- Retry Logic ----



# ---- Envelope Validation ----


class TestValidateEnvelopeRed:

    def test_missing_total_count(self) -> None:
        from datafactory_harvester.sources.ucdp_annual import validate_envelope

        with pytest.raises(ValueError, match="missing keys"):
            validate_envelope({"TotalPages": 1, "Result": []})

    def test_result_is_string_not_list(self) -> None:
        from datafactory_harvester.sources.ucdp_annual import validate_envelope

        with pytest.raises(ValueError, match="expected list"):
            validate_envelope({
                "TotalCount": 0,
                "TotalPages": 1,
                "Result": "not a list",
            })

    def test_empty_dict(self) -> None:
        from datafactory_harvester.sources.ucdp_annual import validate_envelope

        with pytest.raises(ValueError, match="missing keys"):
            validate_envelope({})


# ---- Source Registration ----


class TestUcdpAnnualRegistration:

    def test_registered_in_sources(self) -> None:
        # Importing ucdp_annual auto-registers it
        import datafactory_harvester.sources.ucdp_annual  # noqa: F401
        from datafactory_harvester.sources import list_sources

        assert "ucdp_annual" in list_sources()
