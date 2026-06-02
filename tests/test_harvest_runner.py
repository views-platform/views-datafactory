"""Tests for the shared HarvestRunner (C-164 Pattern #8)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from datafactory_harvester.harvest_runner import HarvestResult, run_harvest

# ---- HarvestResult ----


class TestHarvestResultGreen:

    def test_fields(self) -> None:
        r = HarvestResult(
            source_name="test",
            outcome="success",
            elapsed=1.5,
            data={"n_rows": 100},
        )
        assert r.source_name == "test"
        assert r.outcome == "success"
        assert r.elapsed == 1.5
        assert r.data == {"n_rows": 100}

    def test_frozen(self) -> None:
        r = HarvestResult(
            source_name="test", outcome="success",
            elapsed=0.0, data=None,
        )
        with pytest.raises(AttributeError):
            r.outcome = "failed"  # type: ignore[misc]

    def test_data_defaults_to_none(self) -> None:
        r = HarvestResult(
            source_name="test", outcome="success", elapsed=0.0,
        )
        assert r.data is None

    def test_error_defaults_to_none(self) -> None:
        r = HarvestResult(
            source_name="test", outcome="success", elapsed=0.0,
        )
        assert r.error is None


# ---- run_harvest ----


class TestRunHarvestGreen:

    def test_calls_fetch_fn(self) -> None:
        fetch = MagicMock(return_value={"outcome": "success"})
        run_harvest(
            source_name="test",
            fetch_fn=fetch,
            config_summary={"key": "val"},
        )
        fetch.assert_called_once()

    def test_passes_force_refresh(self) -> None:
        fetch = MagicMock(return_value={})
        run_harvest(
            source_name="test",
            fetch_fn=fetch,
            config_summary={},
            force_refresh=True,
        )
        _, kwargs = fetch.call_args
        assert kwargs["force_refresh"] is True

    def test_passes_fetch_kwargs(self) -> None:
        fetch = MagicMock(return_value={})
        config = object()
        run_harvest(
            source_name="test",
            fetch_fn=fetch,
            config_summary={},
            fetch_kwargs={"config": config},
        )
        _, kwargs = fetch.call_args
        assert kwargs["config"] is config

    def test_returns_success_on_normal_return(self) -> None:
        fetch = MagicMock(return_value={"outcome": "cached"})
        result = run_harvest(
            source_name="test",
            fetch_fn=fetch,
            config_summary={},
        )
        assert result.outcome == "success"
        assert result.data == {"outcome": "cached"}
        assert result.error is None

    def test_returns_failed_on_exception(self) -> None:
        fetch = MagicMock(side_effect=RuntimeError("boom"))
        result = run_harvest(
            source_name="test",
            fetch_fn=fetch,
            config_summary={},
        )
        assert result.outcome == "failed"
        assert result.error == "boom"
        assert result.data is None

    def test_records_elapsed_time(self) -> None:
        fetch = MagicMock(return_value={})
        result = run_harvest(
            source_name="test",
            fetch_fn=fetch,
            config_summary={},
        )
        assert result.elapsed >= 0.0

    def test_prints_banner(self, capsys: pytest.CaptureFixture[str]) -> None:
        fetch = MagicMock(return_value={})
        run_harvest(
            source_name="My Source",
            fetch_fn=fetch,
            config_summary={"Version": "v1", "Output": "/tmp"},
        )
        captured = capsys.readouterr().out
        assert "=" * 60 in captured
        assert "My Source HARVEST" in captured
        assert "Version: v1" in captured
        assert "Output: /tmp" in captured

    def test_prints_fail_on_exception(
        self, capsys: pytest.CaptureFixture[str],
    ) -> None:
        fetch = MagicMock(side_effect=ValueError("bad input"))
        run_harvest(
            source_name="test",
            fetch_fn=fetch,
            config_summary={},
        )
        captured = capsys.readouterr().out
        assert "FAIL: bad input" in captured

    def test_source_name_preserved(self) -> None:
        fetch = MagicMock(return_value={})
        result = run_harvest(
            source_name="V-Dem",
            fetch_fn=fetch,
            config_summary={},
        )
        assert result.source_name == "V-Dem"

    def test_data_contains_fetch_return(self) -> None:
        payload: dict[str, Any] = {
            "outcome": "success", "n_rows": 42,
        }
        fetch = MagicMock(return_value=payload)
        result = run_harvest(
            source_name="test",
            fetch_fn=fetch,
            config_summary={},
        )
        assert result.data is payload
