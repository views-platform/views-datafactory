"""Tests for the shared PipelineRunner (C-164 Pattern #7)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from datafactory_harvester.pipeline_runner import (
    PipelineResult,
    PipelineStep,
    run_pipeline,
)

# ── PipelineStep dataclass ──────────────────────────────────────────


class TestPipelineStepGreen:
    """Green tests for PipelineStep frozen dataclass."""

    def test_fields(self) -> None:
        step = PipelineStep(name="harvest", run=lambda: None)
        assert step.name == "harvest"
        assert step.skip_check is None

    def test_frozen(self) -> None:
        step = PipelineStep(name="harvest", run=lambda: None)
        with pytest.raises(AttributeError):
            step.name = "other"  # type: ignore[misc]

    def test_with_skip_check(self) -> None:
        step = PipelineStep(
            name="harvest",
            run=lambda: None,
            skip_check=lambda: "3 files",
        )
        assert step.skip_check is not None
        assert step.skip_check() == "3 files"


# ── PipelineResult dataclass ────────────────────────────────────────


class TestPipelineResultGreen:
    """Green tests for PipelineResult frozen dataclass."""

    def test_fields(self) -> None:
        r = PipelineResult(
            source_name="TEST",
            steps_run=("harvest", "compile"),
            steps_skipped=(),
            elapsed=1.5,
            step_timings={"harvest": 0.5, "compile": 1.0},
            success=True,
        )
        assert r.source_name == "TEST"
        assert r.success is True
        assert r.elapsed == 1.5
        assert r.steps_run == ("harvest", "compile")

    def test_frozen(self) -> None:
        r = PipelineResult(
            source_name="TEST",
            steps_run=(),
            steps_skipped=(),
            elapsed=0.0,
            step_timings={},
            success=True,
        )
        with pytest.raises(AttributeError):
            r.success = False  # type: ignore[misc]


# ── run_pipeline ────────────────────────────────────────────────────


class TestRunPipelineGreen:
    """Green tests for run_pipeline execution."""

    def test_runs_all_steps(self) -> None:
        calls: list[str] = []
        steps = (
            PipelineStep("a", run=lambda: calls.append("a")),
            PipelineStep("b", run=lambda: calls.append("b")),
        )
        result = run_pipeline(source_name="TEST", steps=steps)
        assert calls == ["a", "b"]
        assert result.steps_run == ("a", "b")
        assert result.steps_skipped == ()
        assert result.success is True

    def test_skip_to_skips_earlier_steps(self) -> None:
        calls: list[str] = []
        steps = (
            PipelineStep("harvest", run=lambda: calls.append("h")),
            PipelineStep("compile", run=lambda: calls.append("c")),
        )
        result = run_pipeline(
            source_name="TEST", steps=steps, skip_to="compile",
        )
        assert calls == ["c"]
        assert result.steps_run == ("compile",)
        assert result.steps_skipped == ("harvest",)

    def test_skip_to_last_step(self) -> None:
        calls: list[str] = []
        steps = (
            PipelineStep("a", run=lambda: calls.append("a")),
            PipelineStep("b", run=lambda: calls.append("b")),
            PipelineStep("c", run=lambda: calls.append("c")),
        )
        result = run_pipeline(
            source_name="TEST", steps=steps, skip_to="c",
        )
        assert calls == ["c"]
        assert result.steps_skipped == ("a", "b")

    def test_skip_check_called_when_skipping(self) -> None:
        check = MagicMock(return_value="3 files")
        steps = (
            PipelineStep(
                "harvest", run=lambda: None, skip_check=check,
            ),
            PipelineStep("compile", run=lambda: None),
        )
        run_pipeline(
            source_name="TEST", steps=steps, skip_to="compile",
        )
        check.assert_called_once()

    def test_skip_check_not_called_when_running(self) -> None:
        check = MagicMock(return_value="3 files")
        steps = (
            PipelineStep(
                "harvest", run=lambda: None, skip_check=check,
            ),
            PipelineStep("compile", run=lambda: None),
        )
        run_pipeline(source_name="TEST", steps=steps)
        check.assert_not_called()

    def test_skip_check_failure_stops_pipeline(self) -> None:
        def bad_check() -> str:
            msg = "No files found"
            raise FileNotFoundError(msg)

        steps = (
            PipelineStep(
                "harvest", run=lambda: None, skip_check=bad_check,
            ),
            PipelineStep("compile", run=lambda: None),
        )
        result = run_pipeline(
            source_name="TEST", steps=steps, skip_to="compile",
        )
        assert result.success is False

    def test_step_failure_stops_pipeline(self) -> None:
        def fail() -> None:
            msg = "boom"
            raise RuntimeError(msg)

        calls: list[str] = []
        steps = (
            PipelineStep("harvest", run=fail),
            PipelineStep("compile", run=lambda: calls.append("c")),
        )
        result = run_pipeline(source_name="TEST", steps=steps)
        assert result.success is False
        assert result.steps_run == ()
        assert calls == []

    def test_step_timings_recorded(self) -> None:
        steps = (
            PipelineStep("harvest", run=lambda: None),
            PipelineStep("compile", run=lambda: None),
        )
        result = run_pipeline(source_name="TEST", steps=steps)
        assert "harvest" in result.step_timings
        assert "compile" in result.step_timings
        assert all(t >= 0 for t in result.step_timings.values())

    def test_elapsed_recorded(self) -> None:
        steps = (PipelineStep("a", run=lambda: None),)
        result = run_pipeline(source_name="TEST", steps=steps)
        assert result.elapsed >= 0

    def test_source_name_preserved(self) -> None:
        steps = (PipelineStep("a", run=lambda: None),)
        result = run_pipeline(source_name="MY-SOURCE", steps=steps)
        assert result.source_name == "MY-SOURCE"

    def test_prints_banner(self, capsys: pytest.CaptureFixture[str]) -> None:
        steps = (PipelineStep("a", run=lambda: None),)
        run_pipeline(
            source_name="TEST",
            steps=steps,
            config_summary={"Key": "Value"},
        )
        out = capsys.readouterr().out
        assert "TEST PIPELINE" in out
        assert "Key: Value" in out

    def test_prints_step_labels(
        self, capsys: pytest.CaptureFixture[str],
    ) -> None:
        steps = (
            PipelineStep("harvest", run=lambda: None),
            PipelineStep("compile", run=lambda: None),
        )
        run_pipeline(source_name="TEST", steps=steps)
        out = capsys.readouterr().out
        assert "[1/2] HARVEST" in out
        assert "[2/2] COMPILE" in out

    def test_prints_skip_detail(
        self, capsys: pytest.CaptureFixture[str],
    ) -> None:
        steps = (
            PipelineStep(
                "harvest",
                run=lambda: None,
                skip_check=lambda: "3 snapshots in data/raw",
            ),
            PipelineStep("compile", run=lambda: None),
        )
        run_pipeline(
            source_name="TEST", steps=steps, skip_to="compile",
        )
        out = capsys.readouterr().out
        assert "skipped" in out.lower()
        assert "3 snapshots in data/raw" in out
