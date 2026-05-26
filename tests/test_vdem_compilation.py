"""Tests for V-Dem compilation — pregridded data to grid.

Green: happy path (shape, features, placement, provenance, sidecars,
       config, multi-cell, NaN coexistence).
Beige: boundary conditions (out-of-bounds pgid, NaN passthrough,
       empty input, month_id out-of-range).
Red: missing source file, missing columns.

Ref: ADR-035 (V-Dem source selection), C-205 (NaN propagation).
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


def _write_vdem_viewpoint(
    path: Path,
    *,
    variables: tuple[str, ...] = ("v2x_libdem",),
    pgids: list[int] | None = None,
    month_ids: list[int] | None = None,
    values_override: dict[str, list[float]] | None = None,
) -> None:
    """Write a minimal V-Dem viewpoint Parquet for compilation."""
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
            vals = [0.5 + 0.1 * i + 0.01 * j for j in range(len(pgids))]
        columns[var] = pa.array(vals, type=pa.float64())

    table = pa.table(columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def _make_vdem_config(
    tmp_path: Path,
    source: Path,
    *,
    variables: tuple[str, ...] = ("v2x_libdem",),
    fill_value: float = float("nan"),
    grid_config: GridConfig | None = None,
    temporal_config: TemporalConfig | None = None,
) -> PregriddedCompilationConfig:
    """Build a V-Dem compilation config with NaN fill (production default)."""
    features = tuple(
        PregriddedFeatureSpec(f"vdem_{v}", v) for v in variables
    )
    return PregriddedCompilationConfig(
        source_path=source,
        grid_config=grid_config or TINY_GRID,
        temporal_config=temporal_config or TINY_TEMPORAL,
        features=features,
        output_dir=tmp_path / "compiled",
        ledger_path=tmp_path / "ledger.jsonl",
        fill_value=fill_value,
    )


# ===================================================================
# GREEN — Config
# ===================================================================


class TestVdemCompilationConfigGreen:
    """Config creation and validation."""

    def test_config_defaults(self) -> None:
        config = PregriddedCompilationConfig(
            source_path=Path("dummy.parquet"),
            features=(
                PregriddedFeatureSpec("vdem_v2x_libdem", "v2x_libdem"),
            ),
        )
        assert config.output_dtype == "float32"
        assert config.fill_value == 0.0
        assert config.pgid_field == "pgid"

    def test_config_frozen(self) -> None:
        config = PregriddedCompilationConfig(
            source_path=Path("dummy.parquet"),
            features=(
                PregriddedFeatureSpec("vdem_v2x_libdem", "v2x_libdem"),
            ),
        )
        with pytest.raises(AttributeError):
            config.output_dtype = "float64"  # type: ignore[misc]

    def test_empty_features_rejected(self) -> None:
        with pytest.raises(ValueError):
            PregriddedCompilationConfig(
                source_path=Path("dummy.parquet"),
                features=(),
            )

    def test_duplicate_feature_names_rejected(self) -> None:
        with pytest.raises(ValueError):
            PregriddedCompilationConfig(
                source_path=Path("dummy.parquet"),
                features=(
                    PregriddedFeatureSpec("vdem_dup", "v2x_libdem"),
                    PregriddedFeatureSpec("vdem_dup", "v2xcl_dmove"),
                ),
            )


# ===================================================================
# GREEN — Compilation
# ===================================================================


class TestVdemCompilationGreen:
    """Happy-path compilation."""

    def test_produces_correct_shape(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(source, variables=("v2x_libdem",))
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert grid.ndim == 4
        assert grid.shape[3] == 1

    def test_feature_names_have_vdem_prefix(
        self, tmp_path: Path,
    ) -> None:
        variables = ("v2x_libdem", "v2xcl_dmove")
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(source, variables=variables)
        config = _make_vdem_config(tmp_path, source, variables=variables)

        result_dir = compile_pregridded(config)
        features = json.loads(
            (result_dir / "feature_names.json").read_text(),
        )
        assert features == ["vdem_v2x_libdem", "vdem_v2xcl_dmove"]

    def test_values_placed_correctly(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source, pgids=[1], month_ids=[1],
            values_override={"v2x_libdem": [0.73]},
        )
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert grid[0, 0, 0, 0] == pytest.approx(0.73, rel=1e-3)

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(source, pgids=[1], month_ids=[1])
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)

        prov = json.loads((result_dir / "provenance.json").read_text())
        assert "grid_shape" in prov
        assert "feature_names" in prov
        assert "source_digest" in prov

        ledger = config.ledger_path.read_text().strip()
        assert len(ledger.splitlines()) >= 1
        entry = json.loads(ledger.splitlines()[-1])
        assert "source_digest" in entry
        assert "output_digest" in entry

    def test_sidecar_files_written(self, tmp_path: Path) -> None:
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(source, pgids=[1], month_ids=[1])
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)

        pgids_arr = np.load(result_dir / "pgids.npy")
        assert pgids_arr.ndim == 2
        assert pgids_arr.shape == (
            TINY_GRID.nrow, TINY_GRID.ncol,
        )

        time_steps = np.load(result_dir / "time_steps.npy")
        assert time_steps.ndim == 1
        assert len(time_steps) == TINY_TEMPORAL.n_steps

    def test_multiple_cells_and_months(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source,
            pgids=[1, 1, 2, 2],
            month_ids=[1, 2, 1, 2],
            values_override={
                "v2x_libdem": [0.1, 0.2, 0.3, 0.4],
            },
        )
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert grid[0, 0, 0, 0] == pytest.approx(0.1, rel=1e-3)
        assert grid[1, 0, 0, 0] == pytest.approx(0.2, rel=1e-3)
        assert grid[0, 0, 1, 0] == pytest.approx(0.3, rel=1e-3)
        assert grid[1, 0, 1, 0] == pytest.approx(0.4, rel=1e-3)

    def test_nan_and_valid_coexist_in_same_row(
        self, tmp_path: Path,
    ) -> None:
        """C-205: A row with one NaN variable and one valid variable
        should place the valid value and leave NaN for the other."""
        variables = ("v2x_libdem", "v2xcl_dmove")
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source,
            variables=variables,
            pgids=[1],
            month_ids=[1],
            values_override={
                "v2x_libdem": [float("nan")],
                "v2xcl_dmove": [0.85],
            },
        )
        config = _make_vdem_config(
            tmp_path, source, variables=variables,
        )

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert np.isnan(grid[0, 0, 0, 0])
        assert grid[0, 0, 0, 1] == pytest.approx(0.85, rel=1e-3)

    def test_multiple_features(self, tmp_path: Path) -> None:
        variables = ("v2x_libdem", "v2xcl_dmove", "v2x_polyarchy")
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source,
            variables=variables,
            pgids=[1],
            month_ids=[1],
        )
        config = _make_vdem_config(
            tmp_path, source, variables=variables,
        )

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert grid.shape[3] == 3
        features = json.loads(
            (result_dir / "feature_names.json").read_text(),
        )
        assert len(features) == 3


# ===================================================================
# BEIGE — Boundary conditions
# ===================================================================


class TestVdemCompilationBeige:
    """Boundary conditions."""

    def test_out_of_bounds_pgid_skipped(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source, pgids=[1, 999999], month_ids=[1, 1],
        )
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        assert (result_dir / "grid.npy").exists()

    def test_nan_value_remains_nan_in_grid(
        self, tmp_path: Path,
    ) -> None:
        """C-205: NaN in viewpoint must remain NaN in compiled grid,
        not silently become 0.0."""
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source,
            pgids=[1],
            month_ids=[1],
            values_override={"v2x_libdem": [float("nan")]},
        )
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert np.isnan(grid[0, 0, 0, 0]), (
            f"NaN source value became {grid[0, 0, 0, 0]} — "
            f"fill_value must be NaN for V-Dem (C-205)"
        )

    def test_unmapped_pgid_cell_is_nan(
        self, tmp_path: Path,
    ) -> None:
        """Cells with no viewpoint data should be NaN, not 0.0."""
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source, pgids=[1], month_ids=[1],
        )
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert np.isnan(grid[0, 0, 1, 0]), (
            f"Unfilled cell is {grid[0, 0, 1, 0]}, expected NaN"
        )

    def test_empty_input_produces_nan_grid(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(source, pgids=[], month_ids=[])
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert np.all(np.isnan(grid))

    def test_month_id_out_of_range_skipped(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source, pgids=[1, 1], month_ids=[1, 9999],
        )
        config = _make_vdem_config(tmp_path, source)

        result_dir = compile_pregridded(config)
        grid = np.load(result_dir / "grid.npy")
        assert not np.isnan(grid[0, 0, 0, 0])


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestVdemCompilationRed:
    """Failure paths."""

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        config = _make_vdem_config(
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
            "v2x_libdem": pa.array([0.5], type=pa.float64()),
        })
        source.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, source)

        config = _make_vdem_config(tmp_path, source)
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

        config = _make_vdem_config(tmp_path, source)
        with pytest.raises(ValueError):
            compile_pregridded(config)
