"""Tests for V-Dem compilation — pregridded data to grid.

Green: happy path (shape, features, placement).
Beige: boundary conditions (out-of-bounds pgid).
Red: missing source file.

Ref: ADR-035 (V-Dem source selection).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def _write_vdem_viewpoint(
    path: Path,
    *,
    variables: tuple[str, ...] = ("v2x_libdem",),
    pgids: list[int] | None = None,
    month_ids: list[int] | None = None,
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
        values = [0.5 + 0.1 * i + 0.01 * j for j in range(len(pgids))]
        columns[var] = pa.array(values, type=pa.float64())

    table = pa.table(columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


# ===================================================================
# GREEN — Compilation
# ===================================================================


class TestVdemCompilationGreen:
    """Happy-path compilation."""

    def test_produces_correct_shape(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(source, variables=("v2x_libdem",))

        config = PregriddedCompilationConfig(
            source_path=source,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                start_year=1980, end_year=1980,
            ),
            features=(
                PregriddedFeatureSpec(
                    "vdem_v2x_libdem", "v2x_libdem",
                ),
            ),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        result_dir = compile_pregridded(config)

        grid = np.load(result_dir / "grid.npy")
        assert grid.ndim == 4
        assert grid.shape[3] == 1  # 1 feature

    def test_feature_names_have_vdem_prefix(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source,
            variables=("v2x_libdem", "v2xcl_dmove"),
        )

        config = PregriddedCompilationConfig(
            source_path=source,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                start_year=1980, end_year=1980,
            ),
            features=(
                PregriddedFeatureSpec(
                    "vdem_v2x_libdem", "v2x_libdem",
                ),
                PregriddedFeatureSpec(
                    "vdem_v2xcl_dmove", "v2xcl_dmove",
                ),
            ),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        result_dir = compile_pregridded(config)

        features = json.loads(
            (result_dir / "feature_names.json").read_text()
        )
        assert features == [
            "vdem_v2x_libdem", "vdem_v2xcl_dmove",
        ]

    def test_values_placed_correctly(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source,
            variables=("v2x_libdem",),
            pgids=[1],
            month_ids=[1],
        )

        config = PregriddedCompilationConfig(
            source_path=source,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                start_year=1980, end_year=1980,
            ),
            features=(
                PregriddedFeatureSpec(
                    "vdem_v2x_libdem", "v2x_libdem",
                ),
            ),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        result_dir = compile_pregridded(config)

        grid = np.load(result_dir / "grid.npy")
        # pgid 1 → row 0, col 0; month_id 1 → time_idx 0
        assert grid[0, 0, 0, 0] != 0.0


# ===================================================================
# BEIGE — Boundary conditions
# ===================================================================


class TestVdemCompilationBeige:
    """Boundary conditions."""

    def test_out_of_bounds_pgid_skipped(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "vdem_v1.parquet"
        _write_vdem_viewpoint(
            source,
            variables=("v2x_libdem",),
            pgids=[1, 999999],
            month_ids=[1, 1],
        )

        config = PregriddedCompilationConfig(
            source_path=source,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                start_year=1980, end_year=1980,
            ),
            features=(
                PregriddedFeatureSpec(
                    "vdem_v2x_libdem", "v2x_libdem",
                ),
            ),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        # Should not crash, just skip the bad pgid
        result_dir = compile_pregridded(config)
        assert (result_dir / "grid.npy").exists()


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestVdemCompilationRed:
    """Failure paths."""

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        config = PregriddedCompilationConfig(
            source_path=tmp_path / "nonexistent.parquet",
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(),
            features=(
                PregriddedFeatureSpec(
                    "vdem_v2x_libdem", "v2x_libdem",
                ),
            ),
            output_dir=tmp_path / "compiled",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with pytest.raises(FileNotFoundError):
            compile_pregridded(config)
