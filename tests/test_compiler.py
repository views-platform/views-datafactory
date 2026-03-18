"""Tests for datafactory_compiler -- grid compilation.

Tests use a tiny 8-cell grid (resolution=90 deg) and synthetic
events to keep tests fast and readable.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_compiler.compiler import compile_grid
from datafactory_compiler.config import CompilationConfig
from datafactory_compiler.strategies import count, get_strategy, max_best, sum_best
from datafactory_grid.config import GridConfig
from datafactory_grid.temporal_config import TemporalConfig

# ---- Helpers ----

TINY_GRID = GridConfig(resolution=90.0)  # 8 cells
TINY_TEMPORAL = TemporalConfig(start_year=2024, end_year=2024)  # 12 months


def _make_parquet(path: Path, events: list[dict]) -> Path:
    """Write events to a Parquet file."""
    if not events:
        # Write an empty table with the right columns
        table = pa.table({
            "id": pa.array([], type=pa.int64()),
            "latitude": pa.array([], type=pa.float64()),
            "longitude": pa.array([], type=pa.float64()),
            "date_start": pa.array([], type=pa.string()),
            "best": pa.array([], type=pa.int64()),
        })
    else:
        all_fields = sorted({k for ev in events for k in ev})
        columns = {f: [ev.get(f) for ev in events] for f in all_fields}
        pa_columns = {n: pa.array(v, from_pandas=True) for n, v in columns.items()}
        table = pa.table(pa_columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def _make_events() -> list[dict]:
    """Create 3 synthetic events at known locations and dates."""
    return [
        {
            "id": 1,
            "latitude": -45.0,   # Cell 1 (bottom-left quadrant)
            "longitude": -90.0,
            "date_start": "2024-01-15",
            "best": 10,
        },
        {
            "id": 2,
            "latitude": -45.0,   # Same cell as event 1
            "longitude": -90.0,
            "date_start": "2024-01-20",
            "best": 5,
        },
        {
            "id": 3,
            "latitude": 45.0,    # Different cell (top-left quadrant)
            "longitude": -90.0,
            "date_start": "2024-03-10",
            "best": 20,
        },
    ]


# ---- Strategies ----


class TestStrategiesGreen:

    def test_count(self) -> None:
        events = [{"best": 10}, {"best": 5}]
        assert count(events) == 2.0

    def test_sum_best(self) -> None:
        events = [{"best": 10}, {"best": 5}]
        assert sum_best(events) == 15.0

    def test_max_best(self) -> None:
        events = [{"best": 10}, {"best": 5}, {"best": 20}]
        assert max_best(events) == 20.0

    def test_sum_best_with_none(self) -> None:
        events = [{"best": 10}, {"best": None}]
        assert sum_best(events) == 10.0

    def test_get_strategy_valid(self) -> None:
        fn = get_strategy("count")
        assert fn is count

    def test_get_strategy_invalid(self) -> None:
        with pytest.raises(KeyError, match="Unknown"):
            get_strategy("nonexistent")


# ---- CompilationConfig ----


class TestCompilationConfigGreen:

    def test_defaults(self, tmp_path: Path) -> None:
        cfg = CompilationConfig(source_path=tmp_path / "test.parquet")
        assert len(cfg.features) == 2
        assert cfg.lat_field == "latitude"

    def test_frozen(self, tmp_path: Path) -> None:
        cfg = CompilationConfig(source_path=tmp_path / "test.parquet")
        with pytest.raises(AttributeError):
            cfg.lat_field = "lat"  # type: ignore[misc]


class TestCompilationConfigBeige:

    def test_rejects_empty_features(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="features"):
            CompilationConfig(
                source_path=tmp_path / "test.parquet",
                features=(),
            )

    def test_source_path_validated_at_compile_time(self, tmp_path: Path) -> None:
        """source_path is not validated at config time — only at compile time."""
        cfg = CompilationConfig(source_path=tmp_path / "nope.parquet")
        # Config construction succeeds; compile_grid will raise FileNotFoundError
        assert cfg.source_path == tmp_path / "nope.parquet"


# ---- Compile Grid ----


class TestCompileGridGreen:

    def test_produces_correct_shape(self, tmp_path: Path) -> None:
        events = _make_events()
        src = _make_parquet(tmp_path / "source.parquet", events)
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(("event_count", "count"), ("fatalities", "sum_best")),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        result = compile_grid(cfg)

        grid = np.load(result / "grid.npy")
        assert grid.shape == (8, 12, 2)  # 8 cells, 12 months, 2 features
        assert grid.dtype == np.float32

    def test_produces_sidecar_arrays(self, tmp_path: Path) -> None:
        events = _make_events()
        src = _make_parquet(tmp_path / "source.parquet", events)
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        result = compile_grid(cfg)

        pgids = np.load(result / "pgids.npy")
        assert len(pgids) == 8
        assert pgids[0] == 1

        time_steps = np.load(result / "time_steps.npy")
        assert len(time_steps) == 12

        feature_names = json.loads((result / "feature_names.json").read_text())
        assert feature_names == ["event_count", "fatalities"]

    def test_event_count_values(self, tmp_path: Path) -> None:
        """Two events in cell 1 January, one event in cell 5 March."""
        events = _make_events()
        src = _make_parquet(tmp_path / "source.parquet", events)
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(("event_count", "count"),),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        # Find which cell lat=-45, lon=-90 maps to
        from datafactory_grid.generator import latlon_to_pgid

        pgid_sw = int(latlon_to_pgid(-45.0, -90.0, TINY_GRID))
        pgid_nw = int(latlon_to_pgid(45.0, -90.0, TINY_GRID))

        # January (index 0): 2 events in cell pgid_sw
        assert grid[pgid_sw - 1, 0, 0] == 2.0
        # March (index 2): 1 event in cell pgid_nw
        assert grid[pgid_nw - 1, 2, 0] == 1.0
        # All other cells/months should be 0
        assert grid.sum() == 3.0

    def test_sum_best_values(self, tmp_path: Path) -> None:
        events = _make_events()
        src = _make_parquet(tmp_path / "source.parquet", events)
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(("fatalities", "sum_best"),),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        from datafactory_grid.generator import latlon_to_pgid

        pgid_sw = int(latlon_to_pgid(-45.0, -90.0, TINY_GRID))
        # January: best=10 + best=5 = 15
        assert grid[pgid_sw - 1, 0, 0] == 15.0

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        events = _make_events()
        src = _make_parquet(tmp_path / "source.parquet", events)
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        result = compile_grid(cfg)

        # Provenance JSON
        prov = json.loads((result / "provenance.json").read_text())
        assert "source_digest" in prov
        assert "output_digest" in prov
        assert prov["grid_shape"] == [8, 12, 2]

        # Ledger entry
        assert cfg.ledger_path.exists()
        entry = json.loads(
            cfg.ledger_path.read_text().strip().splitlines()[-1]
        )
        assert entry["dataset"] == "compilation"
        assert "source_digest" in entry

    def test_deterministic(self, tmp_path: Path) -> None:
        """Same input twice produces identical output digest."""
        events = _make_events()
        src = _make_parquet(tmp_path / "source.parquet", events)

        cfg1 = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "out1",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        cfg2 = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "out2",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(cfg1)
        compile_grid(cfg2)

        prov1 = json.loads((tmp_path / "out1" / "provenance.json").read_text())
        prov2 = json.loads((tmp_path / "out2" / "provenance.json").read_text())
        assert prov1["output_digest"] == prov2["output_digest"]


class TestCompileGridBeige:

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        cfg = CompilationConfig(
            source_path=tmp_path / "nonexistent.parquet",
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        with pytest.raises(FileNotFoundError, match="Source file"):
            compile_grid(cfg)

    def test_missing_lat_column_raises(self, tmp_path: Path) -> None:
        events = [{"id": 1, "longitude": 0.0, "date_start": "2024-01-01"}]
        src = _make_parquet(tmp_path / "source.parquet", events)
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        with pytest.raises(ValueError, match="missing required columns"):
            compile_grid(cfg)

    def test_events_outside_temporal_range_skipped(self, tmp_path: Path) -> None:
        events = [
            {
                "id": 1,
                "latitude": -45.0,
                "longitude": -90.0,
                "date_start": "1970-01-01",  # Before 2024
                "best": 10,
            },
        ]
        src = _make_parquet(tmp_path / "source.parquet", events)
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")
        assert grid.sum() == 0.0  # All zeros — event was skipped
