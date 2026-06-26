"""Tests for bounded-memory compilation via open_memmap.

Verifies that compile_grid and compile_pregridded use memory-mapped
arrays instead of in-memory np.full(), that temp files are cleaned
up after compilation, and that output is bit-identical to the
in-memory approach. Also tests columnar extraction (C-144).

Green: memmap output correctness, temp cleanup, determinism,
       columnar extraction, filtered aggregation.
Beige: disk space pre-flight check, empty bins after filter.
Red: temp file cleanup on failure.

Ref: ADR-037 (bounded-memory compilation), C-223, C-144.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_compilation.compilation_config import (
    CompilationConfig,
    FeatureSpec,
)
from datafactory_compilation.grid_compilation import (
    _place_events,
    compile_grid,
)
from datafactory_compilation.pregridded_compilation import (
    PregriddedCompilationConfig,
    PregriddedFeatureSpec,
    compile_pregridded,
)
from datafactory_priogrid.grid_config import GridConfig
from datafactory_priogrid.temporal_config import TemporalConfig

TINY_GRID = GridConfig(resolution=90.0)
TINY_TEMPORAL = TemporalConfig(start_year=2024, end_year=2024)


def _make_event_parquet(path: Path) -> Path:
    """Write synthetic events for grid compilation."""
    events = pa.table({
        "id": pa.array([1, 2, 3], type=pa.int64()),
        "latitude": pa.array([-45.0, -45.0, 45.0]),
        "longitude": pa.array([-90.0, -90.0, -90.0]),
        "date_start": pa.array(
            ["2024-01-15", "2024-01-20", "2024-03-10"]
        ),
        "best": pa.array([10, 5, 20], type=pa.int64()),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(events, path)
    return path


def _make_pregridded_parquet(path: Path) -> Path:
    """Write synthetic pregridded data for pregridded compilation."""
    table = pa.table({
        "pgid": pa.array([1, 1, 2, 2], type=pa.int32()),
        "month_id": pa.array([529, 530, 529, 530], type=pa.int32()),
        "v2x_libdem": pa.array([0.5, 0.6, 0.7, 0.8]),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


# ---- Green: Memmap output correctness ----


class TestMemmapCompilationGreen:

    def test_grid_compilation_produces_valid_output(
        self, tmp_path: Path,
    ) -> None:
        """compile_grid with memmap produces correct npy output."""
        src = _make_event_parquet(tmp_path / "source.parquet")
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(FeatureSpec("event_count", "count"),),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        result = compile_grid(cfg)
        grid = np.load(result / "grid.npy")
        assert grid.shape == (12, 2, 4, 1)
        assert grid.dtype == np.float32
        assert grid.sum() == 3.0

    def test_pregridded_compilation_produces_valid_output(
        self, tmp_path: Path,
    ) -> None:
        """compile_pregridded with memmap produces correct npy output."""
        src = _make_pregridded_parquet(tmp_path / "source.parquet")
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TemporalConfig(
                start_year=2024, end_year=2024,
            ),
            features=(
                PregriddedFeatureSpec("libdem", "v2x_libdem"),
            ),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        result = compile_pregridded(cfg)
        grid = np.load(result / "grid.npy")
        assert grid.shape == (12, 2, 4, 1)
        assert grid.dtype == np.float32
        assert grid.max() > 0

    def test_no_temp_files_after_grid_compilation(
        self, tmp_path: Path,
    ) -> None:
        """No .npy temp files left in output dir after compilation."""
        src = _make_event_parquet(tmp_path / "source.parquet")
        out_dir = tmp_path / "output"
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(FeatureSpec("event_count", "count"),),
            output_dir=out_dir,
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(cfg)
        npy_files = sorted(out_dir.glob("*.npy"))
        expected = {"grid.npy", "pgids.npy", "time_steps.npy"}
        assert {f.name for f in npy_files} == expected

    def test_no_temp_files_after_pregridded_compilation(
        self, tmp_path: Path,
    ) -> None:
        """No .npy temp files left in output dir after compilation."""
        src = _make_pregridded_parquet(tmp_path / "source.parquet")
        out_dir = tmp_path / "output"
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TemporalConfig(
                start_year=2024, end_year=2024,
            ),
            features=(
                PregriddedFeatureSpec("libdem", "v2x_libdem"),
            ),
            output_dir=out_dir,
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)
        npy_files = sorted(out_dir.glob("*.npy"))
        expected = {"grid.npy", "pgids.npy", "time_steps.npy"}
        assert {f.name for f in npy_files} == expected

    def test_grid_compilation_deterministic(
        self, tmp_path: Path,
    ) -> None:
        """Two runs produce identical output digests."""
        src = _make_event_parquet(tmp_path / "source.parquet")
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
        p1 = json.loads(
            (tmp_path / "out1" / "provenance.json").read_text()
        )
        p2 = json.loads(
            (tmp_path / "out2" / "provenance.json").read_text()
        )
        assert p1["output_digest"] == p2["output_digest"]

    def test_pregridded_compilation_deterministic(
        self, tmp_path: Path,
    ) -> None:
        """Two runs produce identical output digests."""
        src = _make_pregridded_parquet(tmp_path / "source.parquet")
        features = (
            PregriddedFeatureSpec("libdem", "v2x_libdem"),
        )
        cfg1 = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TemporalConfig(
                start_year=2024, end_year=2024,
            ),
            features=features,
            output_dir=tmp_path / "out1",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        cfg2 = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TemporalConfig(
                start_year=2024, end_year=2024,
            ),
            features=features,
            output_dir=tmp_path / "out2",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg1)
        compile_pregridded(cfg2)
        p1 = json.loads(
            (tmp_path / "out1" / "provenance.json").read_text()
        )
        p2 = json.loads(
            (tmp_path / "out2" / "provenance.json").read_text()
        )
        assert p1["output_digest"] == p2["output_digest"]

    def test_fill_value_nan_with_memmap(
        self, tmp_path: Path,
    ) -> None:
        """fill_value=NaN works correctly with memmap."""
        src = _make_event_parquet(tmp_path / "source.parquet")
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(FeatureSpec("event_count", "count"),),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
            fill_value=float("nan"),
        )
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")
        assert np.isnan(grid[0, 0, 0, 0])


# ---- Beige: disk space pre-flight ----


class TestMemmapCompilationBeige:

    def test_grid_insufficient_disk_raises(
        self, tmp_path: Path,
    ) -> None:
        """compile_grid raises when disk space is insufficient."""
        src = _make_event_parquet(tmp_path / "source.parquet")
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(FeatureSpec("event_count", "count"),),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        mock_usage = type(
            "usage", (), {"total": 100, "used": 100, "free": 0},
        )()
        with (
            patch("shutil.disk_usage", return_value=mock_usage),
            pytest.raises(
                RuntimeError, match="Insufficient disk"
            ),
        ):
            compile_grid(cfg)

    def test_pregridded_insufficient_disk_raises(
        self, tmp_path: Path,
    ) -> None:
        """compile_pregridded raises when disk space is insufficient."""
        src = _make_pregridded_parquet(tmp_path / "source.parquet")
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TemporalConfig(
                start_year=2024, end_year=2024,
            ),
            features=(
                PregriddedFeatureSpec("libdem", "v2x_libdem"),
            ),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        mock_usage = type(
            "usage", (), {"total": 100, "used": 100, "free": 0},
        )()
        with (
            patch("shutil.disk_usage", return_value=mock_usage),
            pytest.raises(
                RuntimeError, match="Insufficient disk"
            ),
        ):
            compile_pregridded(cfg)


# ---- Red: temp cleanup on failure ----


class TestMemmapCompilationRed:

    def test_temp_cleaned_on_grid_failure(
        self, tmp_path: Path,
    ) -> None:
        """Temp memmap file is removed if compilation fails."""
        cfg = CompilationConfig(
            source_path=tmp_path / "nonexistent.parquet",
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        with pytest.raises(FileNotFoundError):
            compile_grid(cfg)
        tmp_npy = list(tmp_path.rglob("_memmap_*.npy"))
        assert tmp_npy == []

    def test_temp_cleaned_on_pregridded_failure(
        self, tmp_path: Path,
    ) -> None:
        """Temp memmap file is removed if compilation fails."""
        src = _make_pregridded_parquet(tmp_path / "source.parquet")
        bad_table = pa.table({
            "pgid": pa.array([1], type=pa.int32()),
            "month_id": pa.array([529], type=pa.int32()),
        })
        pq.write_table(bad_table, src)
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TemporalConfig(
                start_year=2024, end_year=2024,
            ),
            features=(
                PregriddedFeatureSpec("libdem", "v2x_libdem"),
            ),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        with pytest.raises(ValueError, match="missing required"):
            compile_pregridded(cfg)
        tmp_npy = list(tmp_path.rglob("_memmap_*.npy"))
        assert tmp_npy == []


# ---- Green: Columnar extraction (C-144) ----


class TestColumnarExtractionGreen:
    """Verify _place_events uses row-index bins, not event dicts."""

    def test_place_events_returns_row_index_arrays(
        self, tmp_path: Path,
    ) -> None:
        """_place_events returns ndarray row indices, not list[dict]."""
        src = _make_event_parquet(tmp_path / "source.parquet")
        table = pq.read_table(src)
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(FeatureSpec("event_count", "count"),),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        bins, col_arrays = _place_events(table, cfg)

        assert len(bins) > 0
        for key, indices in bins.items():
            assert isinstance(key, tuple)
            assert len(key) == 2
            assert isinstance(indices, np.ndarray)
            assert indices.dtype == np.intp

        assert isinstance(col_arrays, dict)
        for col_name, arr in col_arrays.items():
            assert isinstance(col_name, str)
            assert isinstance(arr, np.ndarray)

    def test_place_events_col_arrays_match_table(
        self, tmp_path: Path,
    ) -> None:
        """col_arrays values match the original table data."""
        src = _make_event_parquet(tmp_path / "source.parquet")
        table = pq.read_table(src)
        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(
                FeatureSpec("best_sum", "sum_field", "best"),
            ),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        bins, col_arrays = _place_events(table, cfg)

        assert "best" in col_arrays
        assert len(col_arrays["best"]) == 3
        assert list(col_arrays["best"]) == [10, 5, 20]

    def test_filtered_feature_with_columnar_lookups(
        self, tmp_path: Path,
    ) -> None:
        """Per-feature filter works correctly with columnar data."""
        events = pa.table({
            "latitude": pa.array([-45.0, -45.0, -45.0]),
            "longitude": pa.array([-90.0, -90.0, -90.0]),
            "date_start": pa.array(
                ["2024-01-15", "2024-01-20", "2024-01-25"],
            ),
            "best": pa.array([10, 5, 20], type=pa.int64()),
            "event_type": pa.array(
                ["battles", "riots", "battles"],
            ),
        })
        src = tmp_path / "source.parquet"
        src.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(events, src)

        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(
                FeatureSpec(
                    "battle_count", "count",
                    filter={"event_type": "battles"},
                ),
                FeatureSpec(
                    "battle_best", "sum_field",
                    filter={"event_type": "battles"},
                    value_field="best",
                ),
                FeatureSpec(
                    "all_count", "count",
                ),
            ),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        # All 3 events land in same cell (lat=-45, lon=-90)
        # battles: events 0 and 2 → count=2, sum=30
        # all: 3 events → count=3
        cell_values = grid[0, :, :, :]
        battle_count = cell_values[:, :, 0].sum()
        battle_best = cell_values[:, :, 1].sum()
        all_count = cell_values[:, :, 2].sum()

        assert battle_count == 2.0
        assert battle_best == 30.0
        assert all_count == 3.0

    def test_place_events_empty_returns_empty(
        self, tmp_path: Path,
    ) -> None:
        """_place_events with no valid events returns empty dicts."""
        table = pa.table({
            "latitude": pa.array([], type=pa.float64()),
            "longitude": pa.array([], type=pa.float64()),
            "date_start": pa.array([], type=pa.string()),
            "best": pa.array([], type=pa.int64()),
        })
        src = tmp_path / "source.parquet"
        src.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, src)

        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(FeatureSpec("event_count", "count"),),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        bins, col_arrays = _place_events(table, cfg)
        assert bins == {}
        assert col_arrays == {}


# ---- Beige: Empty bins after filter (C-144) ----


class TestColumnarExtractionBeige:

    def test_filter_excludes_all_events_produces_fill(
        self, tmp_path: Path,
    ) -> None:
        """Filter that matches no events produces fill value."""
        events = pa.table({
            "latitude": pa.array([-45.0, -45.0]),
            "longitude": pa.array([-90.0, -90.0]),
            "date_start": pa.array(
                ["2024-01-15", "2024-01-20"],
            ),
            "best": pa.array([10, 5], type=pa.int64()),
            "event_type": pa.array(["riots", "riots"]),
        })
        src = tmp_path / "source.parquet"
        src.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(events, src)

        cfg = CompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(
                FeatureSpec(
                    "battle_count", "count",
                    filter={"event_type": "battles"},
                ),
            ),
            output_dir=tmp_path / "output",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")
        assert grid.sum() == 0.0
