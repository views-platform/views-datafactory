"""Performance test: full-scale compilation under time budget.

Addresses C-30: no performance test for full-scale compilation.
The 60-second target (NF-5) covers 259,200 cells x 12 months with
50 realistic events. This test runs on the full PRIO-GRID (not the
tiny 2x4 grid used in unit tests) to catch performance regressions.

Marked @pytest.mark.slow for future gating if needed — currently
runs in the normal test suite (completes in <1s).
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from datafactory_compilation.compilation_config import (
    CompilationConfig,
    FeatureSpec,
)
from datafactory_compilation.grid_compilation import compile_grid
from datafactory_harvester.snapshot_storage import save_event_snapshot
from datafactory_priogrid.grid_config import GridConfig
from datafactory_priogrid.temporal_config import TemporalConfig


def _make_events(n: int = 50) -> list[dict]:
    """Create realistic events spread across conflict zones."""
    rng = np.random.default_rng(42)
    locations = [
        (4.0, 31.5), (2.5, 30.5), (15.5, 32.5),
        (9.0, 38.7), (2.0, 45.3), (33.5, 36.3),
        (33.3, 44.4), (15.4, 44.2), (12.0, -1.5),
        (13.5, 2.1),
    ]
    events = []
    for i in range(n):
        loc = locations[i % len(locations)]
        lat = loc[0] + rng.normal(0, 0.3)
        lon = loc[1] + rng.normal(0, 0.3)
        month = rng.integers(1, 13)
        day = rng.integers(1, 29)
        best = int(rng.exponential(5))
        events.append({
            "id": 100_000 + i,
            "country_id": 200 + (i % 10),
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "date_start": f"2023-{month:02d}-{day:02d}",
            "best": best,
            "high": best + int(rng.exponential(3)),
            "low": max(0, best - int(rng.exponential(2))),
            "type_of_violence": rng.choice([1, 2, 3]),
        })
    return events


@pytest.mark.slow()
class TestFullScaleCompilation:
    """Performance: compile onto the full 259,200-cell grid."""

    def test_compilation_under_60s(self, tmp_path: Path) -> None:
        """Full PRIO-GRID compilation must complete in <60s.

        Uses 50 events across 12 months on the full 360x720 grid.
        This is the minimum viable performance test — real
        production runs have 1.7M events but complete in ~30s.
        """
        events = _make_events(50)
        snap_path = tmp_path / "snapshot.parquet"
        save_event_snapshot(events, snap_path)

        config = CompilationConfig(
            source_path=snap_path,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                start_year=2023, end_year=2023,
            ),
            features=(
                FeatureSpec("ged_sb_count", "count",
                            {"type_of_violence": 1}),
                FeatureSpec("ged_sb_best", "sum_field",
                            {"type_of_violence": 1}),
            ),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        t0 = time.monotonic()
        result = compile_grid(config)
        elapsed = time.monotonic() - t0

        grid = np.load(result / "grid.npy")
        assert grid.shape == (12, 360, 720, 2)
        assert elapsed < 60, (
            f"Full-scale compilation took {elapsed:.1f}s "
            f"(budget: 60s)"
        )
