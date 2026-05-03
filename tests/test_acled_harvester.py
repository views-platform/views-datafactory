"""Tests for ACLED source — mock-based, no network.

Tests config validation, credential resolution, OAuth token
management, pagination, and full fetch_acled orchestration flow.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from datafactory_harvester.sources.acled import (
    ALL_EVENT_TYPES,
    AcledConfig,
    _acquire_token,
    _ensure_token,
    _TokenState,
    fetch_acled,
    fetch_paginated,
    get_acled_credentials,
)

# ---- Config Validation ----


class TestAcledConfigGreen:

    def test_defaults(self) -> None:
        cfg = AcledConfig()
        assert cfg.start_year == 1997
        assert cfg.end_year == 2025
        assert cfg.event_types == ALL_EVENT_TYPES
        assert cfg.page_size == 5000

    def test_frozen(self) -> None:
        cfg = AcledConfig()
        with pytest.raises(AttributeError):
            cfg.start_year = 2020  # type: ignore[misc]

    def test_custom_event_types(self) -> None:
        cfg = AcledConfig(event_types=("Battles", "Protests"))
        assert cfg.event_types == ("Battles", "Protests")


class TestAcledConfigBeige:

    def test_rejects_end_before_start(self) -> None:
        with pytest.raises(ValueError, match="end_year"):
            AcledConfig(start_year=2025, end_year=2024)

    def test_rejects_zero_page_size(self) -> None:
        with pytest.raises(ValueError, match="page_size"):
            AcledConfig(page_size=0)

    def test_rejects_zero_retries(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            AcledConfig(max_retries=0)

    def test_rejects_nonpositive_page_delay(self) -> None:
        with pytest.raises(ValueError, match="page_delay"):
            AcledConfig(page_delay=0)

    def test_rejects_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            AcledConfig(timeout=0)

    def test_rejects_unknown_event_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown event type"):
            AcledConfig(event_types=("Battles", "InvalidType"))


# ---- Credential Resolution ----


class TestCredentialResolutionGreen:

    def test_from_arguments(self) -> None:
        u, p = get_acled_credentials("user", "pass")
        assert u == "user"
        assert p == "pass"

    def test_from_env(self) -> None:
        with patch.dict(
            "os.environ",
            {"ACLED_USERNAME": "envuser", "ACLED_PASSWORD": "envpass"},
        ):
            u, p = get_acled_credentials()
        assert u == "envuser"
        assert p == "envpass"

    def test_args_override_env(self) -> None:
        with patch.dict(
            "os.environ",
            {"ACLED_USERNAME": "envuser", "ACLED_PASSWORD": "envpass"},
        ):
            u, p = get_acled_credentials("arguser", "argpass")
        assert u == "arguser"
        assert p == "argpass"


class TestCredentialResolutionBeige:

    def test_missing_both(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(
                ValueError, match="ACLED_USERNAME and ACLED_PASSWORD"
            ),
        ):
            get_acled_credentials()

    def test_missing_password(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"ACLED_USERNAME": "user"},
                clear=True,
            ),
            pytest.raises(ValueError, match="ACLED_PASSWORD"),
        ):
            get_acled_credentials()

    def test_missing_username(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"ACLED_PASSWORD": "pass"},
                clear=True,
            ),
            pytest.raises(ValueError, match="ACLED_USERNAME"),
        ):
            get_acled_credentials()


# ---- OAuth Token Management ----


class TestTokenManagementGreen:

    def test_acquire_token(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "tok123",
            "expires_in": 86400,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "datafactory_http.retry.requests.request",
            return_value=mock_resp,
        ):
            state = _acquire_token("user", "pass")

        assert state.access_token == "tok123"
        assert state.is_valid

    def test_ensure_token_valid(self) -> None:
        import time

        state = _TokenState(
            access_token="valid",
            expires_at=time.monotonic() + 3600,
        )
        result = _ensure_token(state, "user", "pass")
        assert result is state

    def test_ensure_token_expired_refreshes(self) -> None:
        import time

        expired = _TokenState(
            access_token="old",
            expires_at=time.monotonic() - 10,
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "new_tok",
            "expires_in": 86400,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "datafactory_http.retry.requests.request",
            return_value=mock_resp,
        ):
            result = _ensure_token(expired, "user", "pass")

        assert result.access_token == "new_tok"
        assert result.is_valid


class TestTokenManagementBeige:

    def test_missing_access_token_in_response(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": "invalid_grant"}
        mock_resp.raise_for_status = MagicMock()

        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=mock_resp,
            ),
            pytest.raises(ValueError, match="missing 'access_token'"),
        ):
            _acquire_token("user", "pass")


# ---- Mock API Helpers ----


def _make_acled_response(events: list[dict]) -> dict:
    """Create a valid ACLED API response envelope."""
    return {
        "status": 200,
        "success": True,
        "data": events,
        "count": len(events),
    }


def _make_acled_events(n: int = 3) -> list[dict]:
    """Create minimal valid ACLED events."""
    return [
        {
            "event_id_cnty": f"SOM{i:04d}",
            "event_date": f"2020-01-{i + 1:02d}",
            "event_type": "Battles",
            "sub_event_type": "Armed clash",
            "actor1": f"Group A{i}",
            "actor2": f"Group B{i}",
            "country": "Somalia",
            "admin1": "Mogadishu",
            "latitude": 2.0 + i * 0.1,
            "longitude": 45.0 + i * 0.1,
            "fatalities": i * 5,
            "notes": f"Test event {i}",
            "source": "Test source",
            "source_scale": "National",
        }
        for i in range(1, n + 1)
    ]


def _mock_token_response() -> MagicMock:
    """Create a mock OAuth token response."""
    resp = MagicMock()
    resp.json.return_value = {
        "access_token": "test_token_123",
        "expires_in": 86400,
    }
    resp.raise_for_status = MagicMock()
    return resp


# ---- Full Flow (Mock) ----


class TestFetchAcledGreen:

    def test_full_flow(self, tmp_path: Path) -> None:
        """Mock API: auth -> fetch -> validate -> store -> provenance."""
        events = _make_acled_events(5)
        token_resp = _mock_token_response()

        data_resp = MagicMock()
        data_resp.json.return_value = _make_acled_response(events)
        data_resp.raise_for_status = MagicMock()

        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "provenance" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=[token_resp, data_resp],
            ),
            patch.dict(
                "os.environ",
                {
                    "ACLED_USERNAME": "testuser",
                    "ACLED_PASSWORD": "testpass",
                },
            ),
        ):
            result = fetch_acled(config)

        assert result.exists()
        assert result.suffix == ".parquet"

        ledger = config.ledger_path
        assert ledger.exists()
        entry = json.loads(
            ledger.read_text().strip().splitlines()[-1]
        )
        assert entry["dataset"] == "acled"
        assert entry["outcome"] == "success"
        assert "content_digest" in entry

    def test_skips_when_snapshot_exists(
        self, tmp_path: Path,
    ) -> None:
        """When snapshot and ledger exist, skip fetch."""
        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "provenance" / "ledger.jsonl",
        )

        snap_path = (
            config.data_dir / "acled_2020_2020.parquet"
        )
        snap_path.parent.mkdir(parents=True)
        snap_path.write_text("fake")

        from datafactory_provenance import append_ledger_entry

        append_ledger_entry(
            config.ledger_path, {"content_digest": "abc123"}
        )

        with patch(
            "datafactory_http.retry.requests.request",
        ) as mock_req:
            result = fetch_acled(config)

        mock_req.assert_not_called()
        assert result == snap_path


class TestFetchAcledBeige:

    def test_validation_failure_records_ledger(
        self, tmp_path: Path,
    ) -> None:
        """When validation fails, a failed ledger entry is recorded."""
        bad_events = [{"event_id_cnty": "BAD1"}]
        token_resp = _mock_token_response()

        data_resp = MagicMock()
        data_resp.json.return_value = _make_acled_response(
            bad_events
        )
        data_resp.raise_for_status = MagicMock()

        config = AcledConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "provenance" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=[token_resp, data_resp],
            ),
            patch.dict(
                "os.environ",
                {
                    "ACLED_USERNAME": "testuser",
                    "ACLED_PASSWORD": "testpass",
                },
            ),
            pytest.raises(ValueError, match="Validation failed"),
        ):
            fetch_acled(config)

        assert config.ledger_path.exists()
        entry = json.loads(
            config.ledger_path.read_text().strip().splitlines()[-1]
        )
        assert entry["outcome"] == "failed"


# ---- Pagination ----


class TestPaginationGreen:

    def test_multiple_pages(self, tmp_path: Path) -> None:
        """Page-based pagination fetches all events."""
        page1_events = _make_acled_events(3)
        page2_events = [
            {
                **e,
                "event_id_cnty": f"SOM{i + 10:04d}",
            }
            for i, e in enumerate(
                _make_acled_events(2), start=1
            )
        ]

        token_resp = _mock_token_response()

        resp1 = MagicMock()
        resp1.json.return_value = _make_acled_response(
            page1_events
        )
        resp1.raise_for_status = MagicMock()

        resp2 = MagicMock()
        resp2.json.return_value = _make_acled_response(
            page2_events
        )
        resp2.raise_for_status = MagicMock()

        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            page_size=3,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=[token_resp, resp1, resp2],
            ),
            patch(
                "datafactory_harvester.sources.acled.time.sleep",
            ),
        ):
            events = fetch_paginated(
                config, "user", "pass"
            )

        assert len(events) == 5


    def test_empty_page_terminates(self, tmp_path: Path) -> None:
        """Pagination stops when API returns empty data array."""
        page1_events = _make_acled_events(3)

        token_resp = _mock_token_response()

        resp1 = MagicMock()
        resp1.json.return_value = _make_acled_response(
            page1_events
        )
        resp1.raise_for_status = MagicMock()

        resp_empty = MagicMock()
        resp_empty.json.return_value = _make_acled_response([])
        resp_empty.raise_for_status = MagicMock()

        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            page_size=3,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=[token_resp, resp1, resp_empty],
            ),
            patch(
                "datafactory_harvester.sources.acled.time.sleep",
            ),
        ):
            events = fetch_paginated(
                config, "user", "pass"
            )

        assert len(events) == 3

    def test_token_request_includes_client_id(self) -> None:
        """Token POST body must include client_id=acled."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "tok123",
            "expires_in": 86400,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "datafactory_http.retry.requests.request",
            return_value=mock_resp,
        ) as mock_req:
            _acquire_token("user", "pass")

        call_kwargs = mock_req.call_args[1]
        assert call_kwargs["data"]["client_id"] == "acled"

    def test_page_params_structure(self, tmp_path: Path) -> None:
        """API request sends page, _format, limit, event_date."""
        events = _make_acled_events(2)
        token_resp = _mock_token_response()

        data_resp = MagicMock()
        data_resp.json.return_value = _make_acled_response(
            events
        )
        data_resp.raise_for_status = MagicMock()

        config = AcledConfig(
            start_year=2023,
            end_year=2024,
            page_size=5000,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=[token_resp, data_resp],
            ) as mock_req,
            patch(
                "datafactory_harvester.sources.acled.time.sleep",
            ),
        ):
            fetch_paginated(config, "user", "pass")

        # Second call is the data request (first is token)
        data_call = mock_req.call_args_list[1]
        params = data_call[1]["params"]
        assert params["page"] == 1
        assert params["_format"] == "json"
        assert params["limit"] == 5000
        assert params["event_date"] == "2023-01-01|2024-12-31"
        assert params["event_date_where"] == "BETWEEN"
        assert "offset" not in params

    def test_mid_pagination_token_refresh(
        self, tmp_path: Path,
    ) -> None:
        """Token that expires mid-pagination is refreshed."""
        page1_events = _make_acled_events(3)
        page2_events = _make_acled_events(2)

        token_resp1 = MagicMock()
        token_resp1.json.return_value = {
            "access_token": "tok_first",
            "expires_in": 310,
        }
        token_resp1.raise_for_status = MagicMock()

        token_resp2 = MagicMock()
        token_resp2.json.return_value = {
            "access_token": "tok_refreshed",
            "expires_in": 86400,
        }
        token_resp2.raise_for_status = MagicMock()

        resp1 = MagicMock()
        resp1.json.return_value = _make_acled_response(
            page1_events
        )
        resp1.raise_for_status = MagicMock()

        resp2 = MagicMock()
        resp2.json.return_value = _make_acled_response(
            page2_events
        )
        resp2.raise_for_status = MagicMock()

        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            page_size=3,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        # Monotonic sequence:
        # _acquire_token: expires_at = 0 + 310 = 310
        # _ensure_token (page 1): 5 < 310-300=10 → valid
        # _ensure_token (page 2): 15 < 10 → INVALID → refresh
        # _acquire_token (refresh): expires_at = 15 + 86400
        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=[
                    token_resp1, resp1, token_resp2, resp2,
                ],
            ),
            patch(
                "datafactory_harvester.sources.acled.time.sleep",
            ),
            patch(
                "datafactory_harvester.sources.acled.time.monotonic",
                side_effect=[0.0, 5.0, 15.0, 15.0],
            ),
        ):
            events = fetch_paginated(
                config, "user", "pass"
            )

        assert len(events) == 5


# ---- Characterization (Real Data) ----


class TestAcledCharacterization:
    """Verify validator works against real API response structure."""

    SAMPLE_PATH = (
        Path(__file__).parent.parent / "tests" / "fixtures"
        / "acled_sample.json"
    )

    @pytest.fixture(autouse=True)
    def _ensure_fixture(self, tmp_path: Path) -> None:
        """Use the real sample if available, else skip."""
        desktop_sample = Path.home() / "Desktop" / "ACLED_sample.json"
        if desktop_sample.exists():
            self._sample = desktop_sample
        elif self.SAMPLE_PATH.exists():
            self._sample = self.SAMPLE_PATH
        else:
            pytest.skip("No ACLED sample fixture available")

    def test_sample_has_required_fields(self) -> None:
        """Every event in real sample has all REQUIRED_FIELDS."""
        from datafactory_harvester.sources.acled import (
            REQUIRED_FIELDS,
        )

        data = json.loads(self._sample.read_text())
        events = data["data"]

        for i, ev in enumerate(events):
            missing = REQUIRED_FIELDS - set(ev.keys())
            assert not missing, (
                f"Event {i} missing fields: {missing}"
            )

    def test_sample_field_types_match(self) -> None:
        """Field types in real sample match FIELD_TYPES spec."""
        from datafactory_harvester.sources.acled import (
            FIELD_TYPES,
        )

        data = json.loads(self._sample.read_text())
        events = data["data"]

        for i, ev in enumerate(events):
            for field, expected in FIELD_TYPES.items():
                if field not in ev or ev[field] is None:
                    continue
                assert isinstance(ev[field], expected), (
                    f"Event {i} field {field}: "
                    f"expected {expected}, got "
                    f"{type(ev[field])}"
                )

    def test_sample_response_envelope(self) -> None:
        """Real response has expected envelope structure."""
        data = json.loads(self._sample.read_text())

        assert "data" in data
        assert isinstance(data["data"], list)
        assert "status" in data
        assert "success" in data

    def test_validate_events_passes_on_sample(self) -> None:
        """validate_events accepts real API response events."""
        from datafactory_harvester.event_validation import (
            validate_events,
        )
        from datafactory_harvester.sources.acled import (
            FIELD_TYPES,
            REQUIRED_FIELDS,
        )

        data = json.loads(self._sample.read_text())
        events = data["data"]

        result = validate_events(
            events, REQUIRED_FIELDS, FIELD_TYPES
        )
        assert result.valid, (
            f"Validation failed: {result.errors}"
        )


# ---- Red Team (Adversarial) ----


class TestFetchAcledRed:

    def test_token_endpoint_returns_garbage(self) -> None:
        """Non-JSON response from token endpoint propagates."""
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("No JSON")

        with (
            patch(
                "datafactory_http.retry.requests.request",
                return_value=mock_resp,
            ),
            pytest.raises(ValueError, match="No JSON"),
        ):
            _acquire_token("user", "pass")

    def test_token_response_missing_expires_in_defaults(
        self,
    ) -> None:
        """Missing expires_in falls back to 86400s default."""
        import time

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "tok123",
        }

        before = time.monotonic()
        with patch(
            "datafactory_http.retry.requests.request",
            return_value=mock_resp,
        ):
            state = _acquire_token("user", "pass")

        assert state.access_token == "tok123"
        assert state.expires_at >= before + 86400

    def test_api_returns_non_list_data_silently_corrupts(
        self, tmp_path: Path,
    ) -> None:
        """API data as string silently extends chars — no guard.

        Documents a known weakness: if the API returns a string
        instead of a list for the "data" field, extend() iterates
        characters. This should be caught by downstream validation
        (validate_events), not by fetch_paginated itself.
        """
        token_resp = MagicMock()
        token_resp.json.return_value = {
            "access_token": "tok",
            "expires_in": 86400,
        }
        data_resp = MagicMock()
        data_resp.json.return_value = {
            "data": "abc",
        }

        config = AcledConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=[token_resp, data_resp],
            ),
            patch(
                "datafactory_harvester.sources.acled.time.sleep",
            ),
        ):
            events = fetch_paginated(config, "user", "pass")

        assert events == ["a", "b", "c"]

    def test_api_events_missing_required_field(
        self, tmp_path: Path,
    ) -> None:
        """Events without required fields fail validation loudly."""
        bad_events = [
            {"country": "Somalia", "fatalities": 5},
        ]

        token_resp = MagicMock()
        token_resp.json.return_value = {
            "access_token": "tok",
            "expires_in": 86400,
        }
        data_resp = MagicMock()
        data_resp.json.return_value = {"data": bad_events}

        config = AcledConfig(
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=[token_resp, data_resp],
            ),
            patch(
                "datafactory_harvester.sources.acled.time.sleep",
            ),
            patch.dict(
                "os.environ",
                {
                    "ACLED_USERNAME": "user",
                    "ACLED_PASSWORD": "pass",
                },
            ),
            pytest.raises(ValueError, match="Validation failed"),
        ):
            fetch_acled(config, force_refresh=True)

        ledger = (
            config.ledger_path.read_text()
            .strip()
            .splitlines()
        )
        last = json.loads(ledger[-1])
        assert last["outcome"] == "failed"

    def test_frozen_config_mutation(self) -> None:
        """AcledConfig rejects mutation (frozen enforcement)."""
        cfg = AcledConfig()
        with pytest.raises(AttributeError):
            cfg.page_size = 999  # type: ignore[misc]


# ---- Source Registration ----


class TestAcledRegistration:

    def test_registered_in_sources(self) -> None:
        import datafactory_harvester.sources.acled  # noqa: F401
        from datafactory_harvester.sources import list_sources

        assert "acled" in list_sources()
