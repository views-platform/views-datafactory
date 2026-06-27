"""Tests for UCDP .9 consolidated monthly source — mock-based."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from datafactory_harvester.sources.ucdp_dot9 import (
    DOT9_FIRST_YEAR,
    UcdpDot9Config,
    _dot9_version_string,
    discover_dot9_versions,
    fetch_ucdp_dot9,
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


class TestDot9VersionStringGreen:

    def test_jan_2025(self) -> None:
        assert _dot9_version_string(2025, 1) == "25.9.1"

    def test_dec_2025(self) -> None:
        assert _dot9_version_string(2025, 12) == "25.9.12"

    def test_jan_2018(self) -> None:
        assert _dot9_version_string(2018, 1) == "18.9.1"


# ---- Config ----


class TestDot9ConfigGreen:

    def test_defaults(self) -> None:
        cfg = UcdpDot9Config()
        assert cfg.start_year == DOT9_FIRST_YEAR
        assert cfg.start_month == 1
        assert "dot9" in str(cfg.data_dir)

    def test_frozen(self) -> None:
        cfg = UcdpDot9Config()
        with pytest.raises(AttributeError):
            cfg.start_year = 2020  # type: ignore[misc]


class TestDot9ConfigRed:

    def test_mutation_rejected(self) -> None:
        cfg = UcdpDot9Config()
        with pytest.raises(AttributeError):
            cfg.start_month = 6  # type: ignore[misc]


class TestDot9ADR008:

    def test_invalid_month_raised(self) -> None:
        with pytest.raises(ValueError, match="start_month"):
            UcdpDot9Config(start_month=0)


class TestDot9ConfigBeige:

    def test_rejects_month_0(self) -> None:
        with pytest.raises(ValueError, match="start_month"):
            UcdpDot9Config(start_month=0)

    def test_rejects_month_13(self) -> None:
        with pytest.raises(ValueError, match="start_month"):
            UcdpDot9Config(start_month=13)

    def test_rejects_negative_year(self) -> None:
        with pytest.raises(ValueError, match="start_year"):
            UcdpDot9Config(start_year=-1)

    def test_rejects_zero_rate_limit(self) -> None:
        with pytest.raises(
            ValueError, match="discovery_rate_limit"
        ):
            UcdpDot9Config(discovery_rate_limit=0)

    def test_rejects_zero_max_versions(self) -> None:
        with pytest.raises(ValueError, match="max_versions"):
            UcdpDot9Config(max_versions=0)

    def test_rejects_zero_page_size(self) -> None:
        with pytest.raises(ValueError, match="page_size"):
            UcdpDot9Config(page_size=0)

    def test_rejects_zero_retries(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            UcdpDot9Config(max_retries=0)

    def test_rejects_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            UcdpDot9Config(timeout=0)


# ---- Version Discovery ----


class TestDiscoverDot9VersionsGreen:

    def test_discovers_multiple_versions(self) -> None:
        responses = [
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 30000,
                    "TotalPages": 30,
                    "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 28000,
                    "TotalPages": 28,
                    "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 0,
                    "TotalPages": 0,
                    "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
        ]

        config = UcdpDot9Config(start_year=2025)
        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=responses,
            ),
            patch.dict(
                "os.environ", {"UCDP_API_TOKEN": "test"}
            ),
        ):
            versions = discover_dot9_versions(config)

        assert versions == ["25.9.1", "25.9.2"]

    def test_returns_empty_when_no_versions(self) -> None:
        resp = MagicMock(
            json=MagicMock(return_value={
                "TotalCount": 0,
                "TotalPages": 0,
                "Result": [],
            }),
            raise_for_status=MagicMock(),
        )

        config = UcdpDot9Config(start_year=2025)
        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=resp,
            ),
            patch.dict(
                "os.environ", {"UCDP_API_TOKEN": "test"}
            ),
        ):
            versions = discover_dot9_versions(config)

        assert versions == []


# ---- Envelope Validation in Discovery ----


class TestDiscoverDot9EnvelopeRed:

    def test_dot9_rejects_missing_totalcount(self) -> None:
        """Discovery must reject envelope missing TotalCount."""
        resp = MagicMock(
            json=MagicMock(
                return_value={"TotalPages": 1, "Result": []},
            ),
            raise_for_status=MagicMock(),
        )

        config = UcdpDot9Config(start_year=2025)
        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=resp,
            ),
            patch.dict(
                "os.environ", {"UCDP_API_TOKEN": "test"}
            ),
            pytest.raises(ValueError, match="TotalCount"),
        ):
            discover_dot9_versions(config)


# ---- Full Flow ----


class TestFetchUcdpDot9Green:

    def test_full_flow_with_mock(
        self, tmp_path: Path
    ) -> None:
        events = _make_events(3)

        # Discovery: 1 version, 2nd returns 0
        discover_responses = [
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 3,
                    "TotalPages": 1,
                    "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                json=MagicMock(return_value={
                    "TotalCount": 0,
                    "TotalPages": 0,
                    "Result": [],
                }),
                raise_for_status=MagicMock(),
            ),
        ]

        # Fetch: returns events
        fetch_resp = MagicMock()
        fetch_resp.json.return_value = _make_api_response(
            events
        )
        fetch_resp.raise_for_status = MagicMock()

        config = UcdpDot9Config(
            start_year=2025,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=discover_responses + [fetch_resp],
            ),
            patch.dict(
                "os.environ", {"UCDP_API_TOKEN": "test"}
            ),
        ):
            results = fetch_ucdp_dot9(config)

        assert len(results) == 1
        assert results[0]["outcome"] == "success"
        assert results[0]["version"] == "25.9.1"

        # Provenance recorded
        assert config.ledger_path.exists()
        entry = json.loads(
            config.ledger_path.read_text()
            .strip()
            .splitlines()[-1]
        )
        assert entry["dataset"] == "ucdp_dot9"
        assert entry["version"] == "25.9.1"


# ---- Per-version failure modes (#283, C-276) ----


class TestDot9PerVersionBeige:
    """Boundary: not_served, all-cached."""

    def test_not_served_version_returns_not_served(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ucdp_dot9 import _fetch_dot9_version

        config = UcdpDot9Config(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_api_response([])
        mock_resp.raise_for_status = MagicMock()

        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=mock_resp,
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test"}),
        ):
            result = _fetch_dot9_version(config, "25.9.1")

        assert result["outcome"] == "not_served"
        assert result["version"] == "25.9.1"

    def test_all_versions_cached(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources.ucdp_dot9 import _fetch_dot9_version

        events = _make_events(3)
        config = UcdpDot9Config(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

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
            _fetch_dot9_version(config, "25.9.1")

        r2 = _fetch_dot9_version(config, "25.9.1")
        assert r2["outcome"] == "cached"


class TestDot9PerVersionRed:
    """Adversarial: mixed outcomes, failure isolation, network error."""

    def test_mixed_batch_outcomes(self, tmp_path: Path) -> None:
        config = UcdpDot9Config(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        def mock_fetch_version(_config, version, **_kw):
            outcomes = {
                "25.9.1": {"version": "25.9.1", "outcome": "success",
                           "digest": "abc", "n_events": 3},
                "25.9.2": {"version": "25.9.2", "outcome": "cached",
                           "digest": "def"},
                "25.9.3": {"version": "25.9.3", "outcome": "failed",
                           "errors": ["bad data"]},
            }
            return outcomes[version]

        with (
            patch(
                "datafactory_harvester.sources.ucdp_dot9._fetch_dot9_version",
                side_effect=mock_fetch_version,
            ),
            patch(
                "datafactory_harvester.sources.ucdp_dot9.discover_dot9_versions",
                return_value=["25.9.1", "25.9.2", "25.9.3"],
            ),
        ):
            results = fetch_ucdp_dot9(config)

        assert len(results) == 3
        outcomes = {r["version"]: r["outcome"] for r in results}
        assert outcomes == {
            "25.9.1": "success",
            "25.9.2": "cached",
            "25.9.3": "failed",
        }

    def test_validation_failure_does_not_corrupt_prior_success(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.ucdp_dot9 import _fetch_dot9_version

        events = _make_events(3)
        config = UcdpDot9Config(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        good_resp = MagicMock()
        good_resp.json.return_value = _make_api_response(events)
        good_resp.raise_for_status = MagicMock()

        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=good_resp,
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test"}),
        ):
            r1 = _fetch_dot9_version(config, "25.9.1")

        assert r1["outcome"] == "success"
        snap1 = Path(r1["path"])
        assert snap1.exists()

        bad_events = [{"id": 999}]
        bad_resp = MagicMock()
        bad_resp.json.return_value = _make_api_response(bad_events)
        bad_resp.raise_for_status = MagicMock()

        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=bad_resp,
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test"}),
        ):
            r2 = _fetch_dot9_version(config, "25.9.2")

        assert r2["outcome"] == "failed"
        assert snap1.exists()

    def test_network_error_on_fetch_version(
        self, tmp_path: Path,
    ) -> None:
        import requests

        from datafactory_harvester.sources.ucdp_dot9 import _fetch_dot9_version

        config = UcdpDot9Config(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            max_retries=1,
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=requests.ConnectionError("server down"),
            ),
            patch.dict("os.environ", {"UCDP_API_TOKEN": "test"}),
            pytest.raises(requests.ConnectionError),
        ):
            _fetch_dot9_version(config, "25.9.1")


# ---- Source Registration ----


class TestDot9Registration:

    def test_registered_in_sources(self) -> None:
        import datafactory_harvester.sources.ucdp_dot9  # noqa: F401
        from datafactory_harvester.sources import (
            list_sources,
        )

        assert "ucdp_dot9" in list_sources()
