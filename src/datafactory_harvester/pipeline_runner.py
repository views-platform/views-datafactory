"""Shared pipeline execution runner (C-164 Pattern #7).

Provides run_pipeline() — the common skeleton for all pipeline
scripts: line buffering, banner, per-step timing, skip-to logic,
precondition checks, and error handling.
Source-specific logic stays in the calling script via step closures.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineStep:
    """A single step in a pipeline.

    run: called when this step executes.  Should raise on failure.
    skip_check: called when this step is skipped (--skip-to past it).
        Returns a detail string for the skip message (e.g. "3 files").
        Should raise if precondition data is missing.
    """

    name: str
    run: Callable[[], None]
    skip_check: Callable[[], str] | None = None


@dataclass(frozen=True)
class PipelineResult:
    """Result of running a pipeline."""

    source_name: str
    steps_run: tuple[str, ...]
    steps_skipped: tuple[str, ...]
    elapsed: float
    step_timings: dict[str, float]
    success: bool


def run_pipeline(
    *,
    source_name: str,
    steps: tuple[PipelineStep, ...],
    config_summary: dict[str, str] | None = None,
    skip_to: str | None = None,
) -> PipelineResult:
    """Execute a multi-step pipeline with skip-to support.

    For each step:
    1. If skipped: call skip_check (verify preconditions), print skip label
    2. If running: print step label, call run() with timing, catch errors
    """
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    n = len(steps)
    step_names = [s.name for s in steps]
    skip_idx = step_names.index(skip_to) if skip_to else 0

    print("=" * 60)
    print(f"{source_name} PIPELINE")
    if config_summary:
        for key, value in config_summary.items():
            print(f"{key}: {value}")
    if skip_to:
        print(f"Skipping to: {skip_to}")
    print("=" * 60)
    print()

    t_start = time.monotonic()
    steps_run: list[str] = []
    steps_skipped: list[str] = []
    step_timings: dict[str, float] = {}

    def _fail_result() -> PipelineResult:
        return PipelineResult(
            source_name=source_name,
            steps_run=tuple(steps_run),
            steps_skipped=tuple(steps_skipped),
            elapsed=time.monotonic() - t_start,
            step_timings=step_timings,
            success=False,
        )

    for i, step in enumerate(steps):
        label = f"[{i + 1}/{n}] {step.name.upper()}"

        if i < skip_idx:
            if step.skip_check is not None:
                try:
                    detail = step.skip_check()
                except Exception as e:
                    print(f"FAIL: {e}")
                    return _fail_result()
                print(f"{label} — skipped ({detail})")
            else:
                print(f"{label} — skipped")
            steps_skipped.append(step.name)
            print()
        else:
            print(label)
            t0 = time.monotonic()
            try:
                step.run()
            except Exception as e:
                print(f"  FAIL: {e}")
                return _fail_result()
            dt = time.monotonic() - t0
            step_timings[step.name] = dt
            steps_run.append(step.name)
            print(f"  ({dt:.1f}s)")
            print()

    elapsed = time.monotonic() - t_start
    return PipelineResult(
        source_name=source_name,
        steps_run=tuple(steps_run),
        steps_skipped=tuple(steps_skipped),
        elapsed=elapsed,
        step_timings=step_timings,
        success=True,
    )
