"""Integration test: harvest → compile boundary with realistic data.

Uses a synthetic-but-realistic Parquet that mimics UCDP structure
(key fields, plausible coordinates, real date formats) to test the
data format boundary between harvester output and compiler input.

Runs offline — no network access needed. Part of normal test suite.
Addresses concern C-29.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from datafactory_compilation.compilation_config import (
    CompilationConfig,
    FeatureSpec,
)
from datafactory_compilation.grid_compilation import compile_grid
from datafactory_harvester.snapshot_storage import save_event_snapshot
from datafactory_priogrid.grid_config import GridConfig
from datafactory_priogrid.temporal_config import TemporalConfig


def _make_realistic_events(n: int = 100) -> list[dict]:
    """Create realistic UCDP-like events with plausible coordinates.

    Events are spread across Africa and Middle East — where most
    UCDP conflict events occur. Dates span a single year (2023).
    """
    rng = np.random.default_rng(42)

    # Plausible conflict locations (lat, lon) — Africa + Middle East
    locations = [
        (4.0, 31.5),     # South Sudan
        (2.5, 30.5),     # DRC
        (15.5, 32.5),    # Sudan
        (9.0, 38.7),     # Ethiopia
        (2.0, 45.3),     # Somalia
        (33.5, 36.3),    # Syria
        (33.3, 44.4),    # Iraq
        (15.4, 44.2),    # Yemen
        (12.0, -1.5),    # Burkina Faso
        (13.5, 2.1),     # Niger
    ]

    events = []
    for i in range(n):
        loc = locations[i % len(locations)]
        # Add small random jitter (within ~50km)
        lat = loc[0] + rng.normal(0, 0.3)
        lon = loc[1] + rng.normal(0, 0.3)
        month = rng.integers(1, 13)
        day = rng.integers(1, 29)
        best = int(rng.exponential(5))  # Exponential fatalities
        high = best + int(rng.exponential(3))
        low = max(0, best - int(rng.exponential(2)))

        events.append({
            "id": 100_000 + i,
            "country_id": 200 + (i % 10),
            "country": ["South Sudan", "DRC", "Sudan", "Ethiopia",
                        "Somalia", "Syria", "Iraq", "Yemen",
                        "Burkina Faso", "Niger"][i % 10],
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "date_start": f"2023-{month:02d}-{day:02d}",
            "best": best,
            "high": high,
            "low": low,
            "type_of_violence": rng.choice([1, 2, 3]),
            "event_clarity": 1,
            "code_status": "Clear",
            "where_prec": rng.choice([1, 2, 3]),
            "date_prec": rng.choice([1, 2, 3]),
            "number_of_sources": rng.integers(1, 10),
        })

    return events


TINY_GRID = GridConfig(resolution=90.0)
TINY_TEMPORAL = TemporalConfig(start_year=2023, end_year=2023)


class TestHarvestCompileBoundary:
    """Test the data format boundary between harvester and compiler."""

    def test_harvest_output_compiles_successfully(
        self, tmp_path: Path
    ) -> None:
        """save_event_snapshot → compile_grid with realistic data."""
        events = _make_realistic_events(100)

        # Harvest side: store as Parquet
        snap_path = tmp_path / "snapshot.parquet"
        save_event_snapshot(events, snap_path)

        # Compile side: read Parquet and compile
        config = CompilationConfig(
            source_path=snap_path,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(
                FeatureSpec("event_count", "count"),
                FeatureSpec("fatalities", "sum_field"),
            ),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        result = compile_grid(config)

        # Verify output
        grid = np.load(result / "grid.npy")
        assert grid.shape == (12, 2, 4, 2)  # [T=12, H=2, W=4, C=2]
        assert grid[:, :, :, 0].sum() > 0, "No events placed"
        assert grid[:, :, :, 1].sum() > 0, "No fatalities aggregated"

    def test_all_events_placed(self, tmp_path: Path) -> None:
        """Every event with valid coordinates should be placed."""
        events = _make_realistic_events(100)

        snap_path = tmp_path / "snapshot.parquet"
        save_event_snapshot(events, snap_path)

        config = CompilationConfig(
            source_path=snap_path,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(FeatureSpec("event_count", "count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(config)
        grid = np.load(tmp_path / "compiled" / "grid.npy")

        total_placed = grid[:, :, :, 0].sum()
        assert total_placed == 100, (
            f"Expected 100 events placed, got {total_placed}"
        )

    def test_provenance_chain_complete(self, tmp_path: Path) -> None:
        """Compilation provenance should link to source digest."""
        events = _make_realistic_events(50)

        snap_path = tmp_path / "snapshot.parquet"
        save_event_snapshot(events, snap_path)

        config = CompilationConfig(
            source_path=snap_path,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(config)

        # Check provenance JSON
        prov = json.loads(
            (tmp_path / "compiled" / "provenance.json").read_text()
        )
        assert "source_digest" in prov
        assert "output_digest" in prov
        assert len(prov["source_digest"]) == 16
        assert len(prov["output_digest"]) == 16

        # Check ledger entry
        entry = json.loads(
            tmp_path.joinpath("ledger.jsonl")
            .read_text()
            .strip()
            .splitlines()[-1]
        )
        assert entry["source_digest"] == prov["source_digest"]
        assert entry["output_digest"] == prov["output_digest"]
        assert entry["ledger_version"] == 1

    def test_real_grid_shape(self, tmp_path: Path) -> None:
        """Compile onto the full 259,200-cell grid."""
        events = _make_realistic_events(50)

        snap_path = tmp_path / "snapshot.parquet"
        save_event_snapshot(events, snap_path)

        config = CompilationConfig(
            source_path=snap_path,
            grid_config=GridConfig(),  # Full PRIO-GRID
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(config)
        grid = np.load(tmp_path / "compiled" / "grid.npy")

        assert grid.shape == (12, 360, 720, 2)  # [T, H, W, C]
        assert grid[:, :, :, 0].sum() == 50  # All events placed
