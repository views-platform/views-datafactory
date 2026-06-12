"""Tests for SHDI compilation — pregridded data to grid.

Green: happy path (shape, features, placement, provenance, sidecars,
       config, multi-cell).
Beige: boundary conditions (out-of-bounds pgid, NaN passthrough,
       empty input, month_id out-of-range).
Red: missing source file, missing columns.

Ref: ADR-036 (SHDI source selection), ADR-040 (intensive quantities).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_compilation.pregridded_compilation import (
    PregriddedCompilationConfig,
    PregriddedFeatureSpec,
    compile_pregridded,
)
from datafactory_priogrid import GridConfig, TemporalConfig

TINY_GRID = GridConfig(resolution=90.0)
TINY_TEMPORAL = TemporalConfig(start_year=1980, end_year=1980)

SHDI_VARS = ("shdi", "healthindex", "edindex", "incindex")


def _write_shdi_viewpoint(
    path: Path,
    *,
    variables: tuple[str, ...] = SHDI_VARS,
    pgids: list[int] | None = None,
    month_ids: list[int] | None = None,
    values_override: dict[str, list[float]] | None = None,
) -> None:
    """Write a minimal SHDI viewpoint Parquet for compilation."""
    if pgids is None:
        pgids = [1, 1, 2, 2]
    if month_ids is None:
        month_ids = [1, 2, 1, 2]

    columns: dict[str, pa.Array] = {
        "pgid": pa.array(pgids, type=pa.int32()),
        "month_id": pa.array(month_ids, type=pa.int32()),
    }
    for i, var in enumerate(variables):
        if values_override and var in values_override:
            vals = values_override[var]
        else:
            vals = [
                0.5 + 0.1 * i + 0.01 * j
                for j in range(len(pgids))
            ]
        columns[var] = pa.array(vals, type=pa.float64())

    table = pa.table(columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def _make_shdi_config(
    tmp_path: Path,
    source: Path,
    *,
    variables: tuple[str, ...] = SHDI_VARS,
    grid_config: GridConfig | None = None,
    temporal_config: TemporalConfig | None = None,
) -> PregriddedCompilationConfig:
    """Build an SHDI compilation config with NaN fill."""
    features = tuple(
        PregriddedFeatureSpec(f"shdi_{v}", v) for v in variables
    )
    return PregriddedCompilationConfig(
        source_path=source,
        grid_config=grid_config or TINY_GRID,
        temporal_config=temporal_config or TINY_TEMPORAL,
        features=features,
        output_dir=tmp_path / "compiled",
        ledger_path=tmp_path / "ledger.jsonl",
        fill_value=float("nan"),
    )


# ===================================================================
# GREEN — Compilation
# ===================================================================


class TestShdiCompilationGreen:
    """Happy-path compilation."""

    def test_produces_correct_shape(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(source)
        config = _make_shdi_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert grid.ndim == 4
        assert grid.shape[3] == 4

    def test_feature_names(self, tmp_path: Path) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(source)
        config = _make_shdi_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        features = json.loads(
            (result_dir / "feature_names.json").read_text(),
        )
        assert features == [
            "shdi_shdi",
            "shdi_healthindex",
            "shdi_edindex",
            "shdi_incindex",
        ]

    def test_values_placed_correctly(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(
            source,
            pgids=[1],
            month_ids=[1],
            values_override={
                "shdi": [0.73],
                "healthindex": [0.82],
                "edindex": [0.65],
                "incindex": [0.91],
            },
        )
        config = _make_shdi_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert grid[0, 0, 0, 0] == pytest.approx(0.73, rel=1e-3)
        assert grid[0, 0, 0, 1] == pytest.approx(0.82, rel=1e-3)
        assert grid[0, 0, 0, 2] == pytest.approx(0.65, rel=1e-3)
        assert grid[0, 0, 0, 3] == pytest.approx(0.91, rel=1e-3)

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(source, pgids=[1], month_ids=[1])
        config = _make_shdi_config(tmp_path, source)

        result_dir = compile_pregridded(config)

        prov = json.loads(
            (result_dir / "provenance.json").read_text(),
        )
        assert "grid_shape" in prov
        assert "feature_names" in prov
        assert "source_digest" in prov

        ledger = config.ledger_path.read_text().strip()
        assert len(ledger.splitlines()) >= 1

    def test_sidecar_files_written(self, tmp_path: Path) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(source, pgids=[1], month_ids=[1])
        config = _make_shdi_config(tmp_path, source)

        result_dir = compile_pregridded(config)

        pgids_arr = np.load(result_dir / "pgids.npy")
        assert pgids_arr.ndim == 2

        time_steps = np.load(result_dir / "time_steps.npy")
        assert time_steps.ndim == 1

    def test_multiple_cells_and_months(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(
            source,
            variables=("shdi",),
            pgids=[1, 1, 2, 2],
            month_ids=[1, 2, 1, 2],
            values_override={
                "shdi": [0.1, 0.2, 0.3, 0.4],
            },
        )
        config = _make_shdi_config(
            tmp_path, source, variables=("shdi",),
        )

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert grid[0, 0, 0, 0] == pytest.approx(0.1, rel=1e-3)
        assert grid[1, 0, 0, 0] == pytest.approx(0.2, rel=1e-3)
        assert grid[0, 0, 1, 0] == pytest.approx(0.3, rel=1e-3)
        assert grid[1, 0, 1, 0] == pytest.approx(0.4, rel=1e-3)


# ===================================================================
# BEIGE — Boundary conditions
# ===================================================================


class TestShdiCompilationBeige:
    """Boundary conditions."""

    def test_out_of_bounds_pgid_skipped(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(
            source, pgids=[1, 999999], month_ids=[1, 1],
        )
        config = _make_shdi_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        assert (result_dir / "grid.npy").exists()

    def test_nan_fill_for_unmapped_cells(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(
            source, pgids=[1], month_ids=[1],
        )
        config = _make_shdi_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert np.isnan(grid[0, 0, 1, 0]), (
            f"Unfilled cell is {grid[0, 0, 1, 0]}, expected NaN"
        )

    def test_empty_input_produces_nan_grid(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(source, pgids=[], month_ids=[])
        config = _make_shdi_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert np.all(np.isnan(grid))

    def test_month_id_out_of_range_skipped(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "shdi_v1.parquet"
        _write_shdi_viewpoint(
            source, pgids=[1, 1], month_ids=[1, 9999],
        )
        config = _make_shdi_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert not np.isnan(grid[0, 0, 0, 0])


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestShdiCompilationRed:
    """Failure paths."""

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        config = _make_shdi_config(
            tmp_path, tmp_path / "nonexistent.parquet",
        )
        with pytest.raises(FileNotFoundError):
            compile_pregridded(config)

    def test_missing_pgid_column_raises(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "bad.parquet"
        table = pa.table({
            "wrong_id": pa.array([1], type=pa.int32()),
            "month_id": pa.array([1], type=pa.int32()),
            "shdi": pa.array([0.5], type=pa.float64()),
        })
        source.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, source)

        config = _make_shdi_config(
            tmp_path, source, variables=("shdi",),
        )
        with pytest.raises(ValueError):
            compile_pregridded(config)

    def test_missing_value_column_raises(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "bad.parquet"
        table = pa.table({
            "pgid": pa.array([1], type=pa.int32()),
            "month_id": pa.array([1], type=pa.int32()),
        })
        source.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, source)

        config = _make_shdi_config(
            tmp_path, source, variables=("shdi",),
        )
        with pytest.raises(ValueError):
            compile_pregridded(config)
