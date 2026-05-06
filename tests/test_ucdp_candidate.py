"""Tests for UCDP Candidate Monthly source — mock-based, no network."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from datafactory_harvester.sources.ucdp_candidate import (
    UcdpCandidateConfig,
    _candidate_version_string,
    discover_versions,
    fetch_ucdp_candidate,
)

# ---- Helpers ----


def _make_events(n: int = 3) -> list[dict]:
    return [
        {
            "id": i,
            "country_id": 100 + i,
            "country": f"Country{i}",
            "date_start": f"2025-01-{i + 1:02d}",
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


def _make_api_response(events: list[dict]) -> dict:
    return {
        "TotalCount": len(events),
        "TotalPages": 1,
        "Result": events,
    }


# ---- Version String ----


class TestVersionStringGreen:

    def test_jan_2025(self) -> None:
        assert _candidate_version_string(2025, 1) == "25.0.1"

    def test_dec_2025(self) -> None:
        assert _candidate_version_string(2025, 12) == "25.0.12"

    def test_jan_2026(self) -> None:
        assert _candidate_version_string(2026, 1) == "26.0.1"


# ---- Config ----


class TestCandidateConfigGreen:

    def test_defaults(self) -> None:
        cfg = UcdpCandidateConfig()
        from datafactory_harvester.sources.ucdp_candidate import (
            CANDIDATE_FIRST_YEAR,
        )

        assert cfg.start_year == CANDIDATE_FIRST_YEAR
        assert cfg.start_month == 1

    def test_frozen(self) -> None:
        cfg = UcdpCandidateConfig()
        with pytest.raises(AttributeError):
            cfg.start_year = 2026  # type: ignore[misc]


class TestCandidateConfigRed:

    def test_mutation_rejected(self) -> None:
        cfg = UcdpCandidateConfig()
        with pytest.raises(AttributeError):
            cfg.start_month = 6  # type: ignore[misc]


class TestCandidateADR008:

    _logger_name = "datafactory_harvester.sources.ucdp_candidate"

    def test_invalid_month_logged(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        with (
            caplog.at_level(logging.ERROR, logger=self._logger_name),
            pytest.raises(ValueError, match="start_month"),
        ):
            UcdpCandidateConfig(start_month=0)
        assert len(
            [r for r in caplog.records if r.levelno >= logging.ERROR]
        ) >= 1


class TestCandidateConfigBeige:

    def test_rejects_month_0(self) -> None:
        with pytest.raises(ValueError, match="start_month"):
            UcdpCandidateConfig(start_month=0)

    def test_rejects_month_13(self) -> None:
        with pytest.raises(ValueError, match="start_month"):
            UcdpCandidateConfig(start_month=13)

    def test_rejects_negative_year(self) -> None:
        with pytest.raises(ValueError, match="start_year"):
            UcdpCandidateConfig(start_year=-1)

    def test_rejects_zero_discovery_rate_limit(self) -> None:
        with pytest.raises(ValueError, match="discovery_rate_limit"):
            UcdpCandidateConfig(discovery_rate_limit=0)

    def test_rejects_negative_discovery_rate_limit(self) -> None:
        with pytest.raises(ValueError, match="discovery_rate_limit"):
            UcdpCandidateConfig(discovery_rate_limit=-0.5)

    def test_rejects_zero_max_versions(self) -> None:
        with pytest.raises(ValueError, match="max_versions"):
            UcdpCandidateConfig(max_versions=0)

    def test_rejects_zero_page_size(self) -> None:
        with pytest.raises(ValueError, match="page_size"):
            UcdpCandidateConfig(page_size=0)

    def test_rejects_zero_retries(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            UcdpCandidateConfig(max_retries=0)

    def test_rejects_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            UcdpCandidateConfig(timeout=0)


# ---- Version Discovery ----


class TestDiscoverVersionsGreen:

    def test_discovers_multiple_versions(self) -> None:
        """Mock API: 2 versions available, 3rd returns 0 events."""
        responses = [
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 100, "TotalPages": 1, "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 50, "TotalPages": 1, "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 0, "TotalPages": 0, "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
        ]

        config = UcdpCandidateConfig(start_year=2025)
        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=responses,
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test"}),
        ):
            versions = discover_versions(config)

        assert versions == ["25.0.1", "25.0.2"]

    def test_returns_empty_when_no_versions(self) -> None:
        resp = MagicMock(
            json=MagicMock(return_value={
                "TotalCount": 0, "TotalPages": 0, "Result": [],
            }),
            raise_for_status=MagicMock(),
        )

        config = UcdpCandidateConfig(start_year=2025)
        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=resp,
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test"}),
        ):
            versions = discover_versions(config)

        assert versions == []


# ---- Envelope Validation in Discovery ----


class TestDiscoverVersionsEnvelopeRed:

    def test_candidate_rejects_missing_totalcount(self) -> None:
        """Discovery must reject envelope missing TotalCount."""
        resp = MagicMock(
            json=MagicMock(
                return_value={"TotalPages": 1, "Result": []},
            ),
            raise_for_status=MagicMock(),
        )

        config = UcdpCandidateConfig(start_year=2025)
        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=resp,
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test"}),
            pytest.raises(ValueError, match="TotalCount"),
        ):
            discover_versions(config)


# ---- Digest Caching ----


class TestDigestCachingGreen:

    def test_unchanged_version_records_heartbeat(self, tmp_path: Path) -> None:
        """When digest matches previous, record heartbeat, don't re-store."""
        from datafactory_harvester.sources.ucdp_candidate import _fetch_version

        events = _make_events(3)
        config = UcdpCandidateConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "provenance" / "ledger.jsonl",
        )

        # First fetch — will be "success"
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_api_response(events)
        mock_resp.raise_for_status = MagicMock()

        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=mock_resp,
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test"}),
        ):
            r1 = _fetch_version(config, "25.0.1")

        assert r1["outcome"] == "success"

        # Second fetch — file exists + ledger has digest → "cached"
        # (local-first skip: doesn't touch API)
        r2 = _fetch_version(config, "25.0.1")

        assert r2["outcome"] == "cached"

        # Verify ledger has 1 entry (cached doesn't write)
        lines = config.ledger_path.read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["outcome"] == "success"


# ---- Full Flow ----


class TestFetchUcdpCandidateGreen:

    def test_full_flow_with_mock(self, tmp_path: Path) -> None:
        events = _make_events(3)

        # Discovery: 1 version available, 2nd returns 0
        discover_responses = [
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 3, "TotalPages": 1, "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 0, "TotalPages": 0, "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
        ]

        # Fetch: returns events for the discovered version
        fetch_resp = MagicMock()
        fetch_resp.json.return_value = _make_api_response(events)
        fetch_resp.raise_for_status = MagicMock()

        config = UcdpCandidateConfig(
            start_year=2025,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "provenance" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=discover_responses + [fetch_resp],
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test"}),
        ):
            results = fetch_ucdp_candidate(config)

        assert len(results) == 1
        assert results[0]["outcome"] == "success"
        assert results[0]["version"] == "25.0.1"

        # Provenance recorded
        assert config.ledger_path.exists()
        entry = json.loads(
            config.ledger_path.read_text().strip().splitlines()[-1]
        )
        assert entry["dataset"] == "ucdp_candidate"
        assert entry["version"] == "25.0.1"


# ---- Source Registration ----


class TestCandidateRegistration:

    def test_registered_in_sources(self) -> None:
        import datafactory_harvester.sources.ucdp_candidate  # noqa: F401
        from datafactory_harvester.sources import list_sources

        assert "ucdp_candidate" in list_sources()
