"""Tests for bounded-memory compilation via open_memmap.

Verifies that compile_grid and compile_pregridded use memory-mapped
arrays instead of in-memory np.full(), that temp files are cleaned
up after compilation, and that output is bit-identical to the
in-memory approach.

Green: memmap output correctness, temp cleanup, determinism.
Beige: disk space pre-flight check.
Red: temp file cleanup on failure.

Ref: ADR-037 (bounded-memory compilation), C-223.
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
from datafactory_compilation.grid_compilation import compile_grid
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
