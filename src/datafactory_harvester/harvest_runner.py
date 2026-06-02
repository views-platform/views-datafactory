"""Shared harvest execution wrapper (C-164 Pattern #8).

Provides run_harvest() — the common skeleton for all harvest
scripts: line buffering, banner, timing, and error handling.
Source-specific logic stays in the calling script.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HarvestResult:
    """Uniform result from a harvest run."""

    source_name: str
    outcome: str
    elapsed: float
    data: Any = None
    error: str | None = None


def run_harvest(
    *,
    source_name: str,
    fetch_fn: Callable[..., Any],
    config_summary: dict[str, str],
    force_refresh: bool = False,
    fetch_kwargs: dict[str, Any] | None = None,
) -> HarvestResult:
    """Execute a harvest with standard banner, timing, and error handling.

    Prints banner, calls fetch_fn, catches exceptions, returns result
    with timing. The calling script handles source-specific reporting.
    """
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]

    print("=" * 60)
    print(f"{source_name} HARVEST")
    for key, value in config_summary.items():
        print(f"{key}: {value}")
    print("=" * 60)
    print()

    kwargs = dict(fetch_kwargs or {})
    kwargs["force_refresh"] = force_refresh

    t0 = time.monotonic()
    try:
        raw = fetch_fn(**kwargs)
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"FAIL: {e}")
        return HarvestResult(
            source_name=source_name,
            outcome="failed",
            elapsed=elapsed,
            error=str(e),
        )

    elapsed = time.monotonic() - t0
    return HarvestResult(
        source_name=source_name,
        outcome="success",
        elapsed=elapsed,
        data=raw,
    )
