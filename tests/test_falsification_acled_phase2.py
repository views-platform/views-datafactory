"""Tests from falsification audit (2026-05-03).

F2: event_types config must actually filter API requests when
narrowed from the default (all types).

Both tests describe single-page walks, so `next_cursor: None` ends them
on the first response -- before `time.sleep(page_delay)` is ever
reached. That is why neither patches sleep. If the terminator ever
moves after the sleep, these two start costing `page_delay` seconds
each instead of failing, so the ordering is load-bearing here.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from datafactory_harvester.sources.acled import (
    AcledConfig,
    fetch_paginated,
)


class TestEventTypesFilter:
    """F2: event_types config filters API requests."""

    def test_subset_event_types_sent_as_query_param(
        self, tmp_path: Path,
    ) -> None:
        """Narrowed event_types are sent to API as pipe-separated filter."""
        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            event_types=("Battles", "Riots"),
            page_size=100,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {
            "access_token": "tok",
            "expires_in": 86400,
        }
        token_resp.raise_for_status = MagicMock()

        data_resp = MagicMock()
        data_resp.json.return_value = {
            "data": [],
            "next_cursor": None,
        }
        data_resp.raise_for_status = MagicMock()

        with patch(
            "datafactory_http.retry.requests.request",
            side_effect=[token_resp, data_resp],
        ) as mock_req:
            fetch_paginated(config, "user", "pass")

        data_call = mock_req.call_args_list[1]
        params = data_call[1]["params"]

        assert params["event_type"] == "Battles|Riots"

    def test_all_event_types_omits_filter(
        self, tmp_path: Path,
    ) -> None:
        """Default (all types) does not send event_type filter."""
        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            page_size=100,
            data_dir=tmp_path / "data",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {
            "access_token": "tok",
            "expires_in": 86400,
        }
        token_resp.raise_for_status = MagicMock()

        data_resp = MagicMock()
        data_resp.json.return_value = {
            "data": [],
            "next_cursor": None,
        }
        data_resp.raise_for_status = MagicMock()

        with patch(
            "datafactory_http.retry.requests.request",
            side_effect=[token_resp, data_resp],
        ) as mock_req:
            fetch_paginated(config, "user", "pass")

        data_call = mock_req.call_args_list[1]
        params = data_call[1]["params"]

        assert "event_type" not in params
