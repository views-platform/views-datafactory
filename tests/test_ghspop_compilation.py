"""Tests for pre-gridded compilation — GHS-POP viewpoint Parquet → [T,H,W,C] npy.

Green: happy path (shape, placement, feature names, provenance, fill value).
Beige: empty input, month_id outside range.
Red: missing columns, missing source file.

Ref: ADR-024 (grid invariants), ADR-029 (GHS-POP source).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_priogrid.grid_config import GridConfig
from datafactory_priogrid.temporal_config import TemporalConfig
from datafactory_provenance.constants import VIEWS_EPOCH_YEAR

# Tiny grid: 2×4 = 8 cells at 90° resolution, 3 months
TINY_GRID = GridConfig(resolution=90.0)
TINY_TEMPORAL = TemporalConfig(
    start_year=2020, start_month=1, end_year=2020, end_month=3
)

# VIEWS month_id for Jan 2020: (2020 - 1980) * 12 + 1 = 481
JAN_2020_MID = (2020 - VIEWS_EPOCH_YEAR) * 12 + 1
FEB_2020_MID = JAN_2020_MID + 1
MAR_2020_MID = JAN_2020_MID + 2


def _write_pregridded_parquet(
    path: Path,
    pgids: list[int],
    month_ids: list[int],
    values: list[float],
    value_column: str = "pop_count",
) -> Path:
    """Write a minimal pre-gridded Parquet file."""
    table = pa.table({
        "pgid": pa.array(pgids, type=pa.int32()),
        "month_id": pa.array(month_ids, type=pa.int32()),
        value_column: pa.array(values, type=pa.float64()),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


# ===================================================================
# GREEN — Config
# ===================================================================


class TestPregriddedConfigGreen:
    """PregriddedCompilationConfig defaults and validation."""

    def test_defaults(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        cfg = PregriddedCompilationConfig(
            source_path=tmp_path / "source.parquet",
            features=(PregriddedFeatureSpec("pop_count", "pop_count"),),
        )
        assert cfg.pgid_field == "pgid"
        assert cfg.month_id_field == "month_id"
        assert cfg.output_dtype == "float32"
        assert cfg.fill_value == 0.0

    def test_frozen(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        cfg = PregriddedCompilationConfig(
            source_path=tmp_path / "source.parquet",
            features=(PregriddedFeatureSpec("pop_count", "pop_count"),),
        )
        with pytest.raises(AttributeError):
            cfg.fill_value = 1.0  # type: ignore[misc]

    def test_empty_features_rejected(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
        )

        with pytest.raises(ValueError, match="features"):
            PregriddedCompilationConfig(
                source_path=tmp_path / "source.parquet",
                features=(),
            )

    def test_duplicate_feature_names_rejected(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        with pytest.raises(ValueError, match="duplicate"):
            PregriddedCompilationConfig(
                source_path=tmp_path / "source.parquet",
                features=(
                    PregriddedFeatureSpec("pop", "pop_count"),
                    PregriddedFeatureSpec("pop", "pop_count"),
                ),
            )


# ===================================================================
# GREEN — Compilation
# ===================================================================


class TestPregriddedCompilationGreen:
    """Happy-path pre-gridded compilation."""

    def test_produces_correct_shape(self, tmp_path: Path) -> None:
        """Output grid has [T, H, W, C] shape."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        src = _write_pregridded_parquet(
            tmp_path / "source.parquet",
            pgids=[1],
            month_ids=[JAN_2020_MID],
            values=[100.0],
        )
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("ghspop_pop_count", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        grid = np.load(tmp_path / "compiled" / "grid.npy")
        assert grid.shape == (3, 2, 4, 1)  # T=3, H=2, W=4, C=1

    def test_population_placed_correctly(self, tmp_path: Path) -> None:
        """Known pgid + month_id → correct [t, row, col, channel]."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        # pgid=1 → row=0, col=0 (bottom-left). Jan 2020 → t=0.
        src = _write_pregridded_parquet(
            tmp_path / "source.parquet",
            pgids=[1],
            month_ids=[JAN_2020_MID],
            values=[42.0],
        )
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        grid = np.load(tmp_path / "compiled" / "grid.npy")
        assert grid[0, 0, 0, 0] == pytest.approx(42.0)

    def test_multiple_cells_and_months(self, tmp_path: Path) -> None:
        """Multiple pgids and month_ids placed independently."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        # pgid=1 (row=0, col=0), pgid=5 (row=1, col=0)
        src = _write_pregridded_parquet(
            tmp_path / "source.parquet",
            pgids=[1, 5],
            month_ids=[JAN_2020_MID, MAR_2020_MID],
            values=[10.0, 20.0],
        )
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        grid = np.load(tmp_path / "compiled" / "grid.npy")
        # pgid=1 → (row=0, col=0), Jan → t=0
        assert grid[0, 0, 0, 0] == pytest.approx(10.0)
        # pgid=5 → (row=1, col=0), Mar → t=2
        assert grid[2, 1, 0, 0] == pytest.approx(20.0)

    def test_feature_names_json(self, tmp_path: Path) -> None:
        """feature_names.json contains declared feature names."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        src = _write_pregridded_parquet(
            tmp_path / "source.parquet",
            pgids=[1],
            month_ids=[JAN_2020_MID],
            values=[1.0],
        )
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("ghspop_pop_count", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        names = json.loads(
            (tmp_path / "compiled" / "feature_names.json").read_text()
        )
        assert names == ["ghspop_pop_count"]

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        """provenance.json and ledger entry written."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        src = _write_pregridded_parquet(
            tmp_path / "source.parquet",
            pgids=[1],
            month_ids=[JAN_2020_MID],
            values=[1.0],
        )
        ledger = tmp_path / "ledger.jsonl"
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=ledger,
        )
        compile_pregridded(cfg)

        # provenance.json
        prov = json.loads(
            (tmp_path / "compiled" / "provenance.json").read_text()
        )
        assert "source_digest" in prov
        assert "output_digest" in prov
        assert prov["grid_shape"] == [3, 2, 4, 1]
        assert prov["feature_names"] == ["pop"]

        # ledger
        assert ledger.exists()
        entry = json.loads(ledger.read_text().strip().split("\n")[-1])
        assert "output_digest" in entry
        assert entry["grid_shape"] == [3, 2, 4, 1]

    def test_missing_cells_are_fill_value(self, tmp_path: Path) -> None:
        """Cells without data are filled with fill_value (default 0.0)."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        # Only populate pgid=1. All other cells should be 0.
        src = _write_pregridded_parquet(
            tmp_path / "source.parquet",
            pgids=[1],
            month_ids=[JAN_2020_MID],
            values=[99.0],
        )
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        grid = np.load(tmp_path / "compiled" / "grid.npy")
        # pgid=1 is filled
        assert grid[0, 0, 0, 0] == pytest.approx(99.0)
        # All other cells should be 0
        total = grid.sum()
        assert total == pytest.approx(99.0)

    def test_sidecar_files_written(self, tmp_path: Path) -> None:
        """pgids.npy and time_steps.npy sidecars written."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        src = _write_pregridded_parquet(
            tmp_path / "source.parquet",
            pgids=[1],
            month_ids=[JAN_2020_MID],
            values=[1.0],
        )
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        pgids = np.load(tmp_path / "compiled" / "pgids.npy")
        assert pgids.shape == (2, 4)

        time_steps = np.load(tmp_path / "compiled" / "time_steps.npy")
        assert len(time_steps) == 3

    def test_multiple_features(self, tmp_path: Path) -> None:
        """Multiple features from different value columns."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        table = pa.table({
            "pgid": pa.array([1, 1], type=pa.int32()),
            "month_id": pa.array([JAN_2020_MID, JAN_2020_MID], type=pa.int32()),
            "pop_count": pa.array([100.0, 200.0], type=pa.float64()),
            "pop_density": pa.array([5.0, 10.0], type=pa.float64()),
        })
        src = tmp_path / "source.parquet"
        pq.write_table(table, src)

        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(
                PregriddedFeatureSpec("pop", "pop_count"),
                PregriddedFeatureSpec("density", "pop_density"),
            ),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        grid = np.load(tmp_path / "compiled" / "grid.npy")
        assert grid.shape == (3, 2, 4, 2)
        # Last value wins for duplicate pgid+month_id (or sum — depends on impl)
        # At minimum, both channels should have non-zero values at [0,0,0,:]
        assert grid[0, 0, 0, 0] != 0.0
        assert grid[0, 0, 0, 1] != 0.0


# ===================================================================
# BEIGE — Boundary conditions
# ===================================================================


class TestPregriddedCompilationBeige:
    """Boundary conditions for pre-gridded compilation."""

    def test_empty_input_produces_zero_grid(self, tmp_path: Path) -> None:
        """All-empty Parquet → grid filled with fill_value."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        table = pa.table({
            "pgid": pa.array([], type=pa.int32()),
            "month_id": pa.array([], type=pa.int32()),
            "pop_count": pa.array([], type=pa.float64()),
        })
        src = tmp_path / "source.parquet"
        pq.write_table(table, src)

        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        grid = np.load(tmp_path / "compiled" / "grid.npy")
        assert grid.shape == (3, 2, 4, 1)
        assert grid.sum() == 0.0

    def test_month_id_outside_range_skipped(self, tmp_path: Path) -> None:
        """Month_ids outside temporal range are silently skipped."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        # month_id for Dec 2019 = (2019-1980)*12 + 12 = 480 (before range)
        # month_id for Apr 2020 = 484 (after range, which ends Mar 2020)
        before_range = (2019 - VIEWS_EPOCH_YEAR) * 12 + 12
        after_range = (2020 - VIEWS_EPOCH_YEAR) * 12 + 4

        src = _write_pregridded_parquet(
            tmp_path / "source.parquet",
            pgids=[1, 1, 1],
            month_ids=[before_range, JAN_2020_MID, after_range],
            values=[999.0, 42.0, 888.0],
        )
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        grid = np.load(tmp_path / "compiled" / "grid.npy")
        # Only the in-range value should be placed
        assert grid.sum() == pytest.approx(42.0)

    def test_pgid_outside_range_skipped(self, tmp_path: Path) -> None:
        """PGIDs outside grid bounds are silently skipped."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        n_cells = TINY_GRID.n_cells  # 8
        src = _write_pregridded_parquet(
            tmp_path / "source.parquet",
            pgids=[0, 1, n_cells + 1],
            month_ids=[JAN_2020_MID] * 3,
            values=[999.0, 42.0, 888.0],
        )
        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(cfg)

        grid = np.load(tmp_path / "compiled" / "grid.npy")
        assert grid.sum() == pytest.approx(42.0)


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestPregriddedCompilationRed:
    """Failure modes — fail loud."""

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        cfg = PregriddedCompilationConfig(
            source_path=tmp_path / "nonexistent.parquet",
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        with pytest.raises(FileNotFoundError):
            compile_pregridded(cfg)

    def test_missing_pgid_column_raises(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        # Parquet has wrong column names
        table = pa.table({
            "cell_id": pa.array([1], type=pa.int32()),
            "month_id": pa.array([JAN_2020_MID], type=pa.int32()),
            "pop_count": pa.array([1.0], type=pa.float64()),
        })
        src = tmp_path / "source.parquet"
        pq.write_table(table, src)

        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        with pytest.raises(ValueError, match="missing required columns"):
            compile_pregridded(cfg)

    def test_missing_value_column_raises(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        table = pa.table({
            "pgid": pa.array([1], type=pa.int32()),
            "month_id": pa.array([JAN_2020_MID], type=pa.int32()),
            "wrong_col": pa.array([1.0], type=pa.float64()),
        })
        src = tmp_path / "source.parquet"
        pq.write_table(table, src)

        cfg = PregriddedCompilationConfig(
            source_path=src,
            grid_config=TINY_GRID,
            temporal_config=TINY_TEMPORAL,
            features=(PregriddedFeatureSpec("pop", "pop_count"),),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        with pytest.raises(ValueError, match="missing required columns"):
            compile_pregridded(cfg)
