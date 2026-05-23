"""Tests for GHS-BUILT-S compilation via pregridded compilation.

Green: happy path (config, placement, provenance, sidecar files).
Beige: boundary conditions (out-of-bounds, empty data, out-of-range months).
Red: failure handling (missing columns, missing source).

Ref: ADR-034 (GHS-BUILT-S source), ADR-024 (grid invariants).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ghsbuilts_parquet(
    path: Path,
    pgids: list[int],
    month_ids: list[int],
    built_areas: list[float],
) -> Path:
    """Create a minimal GHS-BUILT-S viewpoint Parquet."""
    table = pa.table({
        "pgid": pa.array(pgids, type=pa.int32()),
        "month_id": pa.array(month_ids, type=pa.int32()),
        "built_area": pa.array(built_areas, type=pa.float64()),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def _compile_ghsbuilts(
    tmp_path: Path,
    pgids: list[int],
    month_ids: list[int],
    built_areas: list[float],
    *,
    start_year: int = 1980,
    start_month: int = 1,
    end_year: int = 1980,
    end_month: int = 12,
    fill_value: float = 0.0,
):
    """Helper: create Parquet, compile, return (output_dir, grid)."""
    from datafactory_compilation.pregridded_compilation import (
        PregriddedCompilationConfig,
        PregriddedFeatureSpec,
        compile_pregridded,
    )
    from datafactory_priogrid import GridConfig, TemporalConfig

    source = tmp_path / "ghsbuilts_v1.parquet"
    _make_ghsbuilts_parquet(source, pgids, month_ids, built_areas)

    config = PregriddedCompilationConfig(
        source_path=source,
        grid_config=GridConfig(),
        temporal_config=TemporalConfig(
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
        ),
        features=(
            PregriddedFeatureSpec(
                "ghsbuilts_built_area", "built_area",
            ),
        ),
        output_dir=tmp_path / "compiled",
        ledger_path=tmp_path / "ledger.jsonl",
        fill_value=fill_value,
    )

    output_dir = compile_pregridded(config)
    grid = np.load(output_dir / "grid.npy")
    return output_dir, grid


# ===================================================================
# GREEN — Config
# ===================================================================


class TestGhsBuiltSCompilationConfigGreen:
    """Config for pregridded compilation with GHS-BUILT-S."""

    def test_config_creation(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        source = tmp_path / "ghsbuilts_v1.parquet"
        _make_ghsbuilts_parquet(
            source, [1], [1], [100.0],
        )

        config = PregriddedCompilationConfig(
            source_path=source,
            features=(
                PregriddedFeatureSpec(
                    "ghsbuilts_built_area", "built_area",
                ),
            ),
            output_dir=tmp_path / "compiled",
        )
        assert config.features[0].name == "ghsbuilts_built_area"
        assert config.features[0].value_field == "built_area"

    def test_feature_spec_fields(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedFeatureSpec,
        )

        spec = PregriddedFeatureSpec(
            "ghsbuilts_built_area", "built_area",
        )
        assert spec.name == "ghsbuilts_built_area"
        assert spec.value_field == "built_area"


# ===================================================================
# GREEN — Compilation
# ===================================================================


class TestGhsBuiltSCompilationGreen:
    """Happy-path compilation placing built_area into grid."""

    def test_places_built_area_correctly(
        self, tmp_path: Path,
    ) -> None:
        output_dir, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1, 1, 720],
            month_ids=[1, 2, 1],
            built_areas=[500.0, 750.0, 1000.0],
        )

        assert grid.shape == (12, 360, 720, 1)
        assert grid[0, 0, 0, 0] == pytest.approx(500.0, rel=1e-3)
        assert grid[1, 0, 0, 0] == pytest.approx(750.0, rel=1e-3)
        assert grid[0, 0, 719, 0] == pytest.approx(
            1000.0, rel=1e-3,
        )

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        output_dir, _ = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[100.0],
        )

        provenance = json.loads(
            (output_dir / "provenance.json").read_text()
        )
        assert "source_digest" in provenance
        assert "output_digest" in provenance
        assert provenance["feature_names"] == [
            "ghsbuilts_built_area",
        ]

        ledger_entries = [
            json.loads(line)
            for line in (tmp_path / "ledger.jsonl")
            .read_text()
            .strip()
            .split("\n")
        ]
        assert len(ledger_entries) == 1
        assert ledger_entries[0]["feature_names"] == [
            "ghsbuilts_built_area",
        ]

    def test_produces_correct_shape(
        self, tmp_path: Path,
    ) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[42.0],
        )

        assert grid.shape == (12, 360, 720, 1)
        assert grid.dtype == np.float32

    def test_multiple_cells_placed(
        self, tmp_path: Path,
    ) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1, 361, 720],
            month_ids=[1, 1, 1],
            built_areas=[10.0, 20.0, 30.0],
        )

        assert grid[0, 0, 0, 0] == pytest.approx(10.0, rel=1e-3)
        assert grid[0, 0, 719, 0] == pytest.approx(30.0, rel=1e-3)

    def test_feature_names_json(self, tmp_path: Path) -> None:
        output_dir, _ = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[1.0],
        )

        names = json.loads(
            (output_dir / "feature_names.json").read_text()
        )
        assert names == ["ghsbuilts_built_area"]

    def test_time_steps_npy(self, tmp_path: Path) -> None:
        output_dir, _ = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[1.0],
        )

        time_steps = np.load(output_dir / "time_steps.npy")
        assert np.issubdtype(time_steps.dtype, np.datetime64)
        assert len(time_steps) == 12

    def test_fill_value_is_zero(self, tmp_path: Path) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[99.0],
        )

        assert grid[0, 0, 1, 0] == 0.0
        assert grid[1, 0, 0, 0] == 0.0


# ===================================================================
# BEIGE — Edge cases
# ===================================================================


class TestGhsBuiltSCompilationBeige:
    """Boundary conditions."""

    def test_out_of_bounds_pgid_skipped(
        self, tmp_path: Path,
    ) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[0, 999999],
            month_ids=[1, 1],
            built_areas=[100.0, 200.0],
        )

        assert grid.sum() == 0.0

    def test_zero_built_area_placed_correctly(
        self, tmp_path: Path,
    ) -> None:
        """Zero is a legitimate value for built-up area, not nodata."""
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[0.0],
        )

        assert grid[0, 0, 0, 0] == 0.0

    def test_empty_input_zero_grid(self, tmp_path: Path) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[],
            month_ids=[],
            built_areas=[],
        )

        assert grid.sum() == 0.0
        assert grid.shape == (12, 360, 720, 1)

    def test_month_id_outside_range_skipped(
        self, tmp_path: Path,
    ) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1, 1, 1],
            month_ids=[0, 1, 13],
            built_areas=[999.0, 42.0, 999.0],
        )

        assert grid[0, 0, 0, 0] == pytest.approx(42.0, rel=1e-3)
        total_placed = (grid != 0.0).sum()
        assert total_placed == 1


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestGhsBuiltSCompilationRed:
    """Adversarial inputs to compilation."""

    def test_missing_pgid_column_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "bad.parquet"
        table = pa.table({
            "cell_id": pa.array([1], type=pa.int32()),
            "month_id": pa.array([1], type=pa.int32()),
            "built_area": pa.array([1.0], type=pa.float64()),
        })
        pq.write_table(table, source)

        config = PregriddedCompilationConfig(
            source_path=source,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                start_year=1980,
                start_month=1,
                end_year=1980,
                end_month=12,
            ),
            features=(
                PregriddedFeatureSpec(
                    "ghsbuilts_built_area", "built_area",
                ),
            ),
            output_dir=tmp_path / "compiled",
        )
        with pytest.raises(ValueError, match="missing"):
            compile_pregridded(config)

    def test_missing_value_column_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "bad.parquet"
        table = pa.table({
            "pgid": pa.array([1], type=pa.int32()),
            "month_id": pa.array([1], type=pa.int32()),
            "wrong_col": pa.array([1.0], type=pa.float64()),
        })
        pq.write_table(table, source)

        config = PregriddedCompilationConfig(
            source_path=source,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                start_year=1980,
                start_month=1,
                end_year=1980,
                end_month=12,
            ),
            features=(
                PregriddedFeatureSpec(
                    "ghsbuilts_built_area", "built_area",
                ),
            ),
            output_dir=tmp_path / "compiled",
        )
        with pytest.raises(ValueError, match="missing"):
            compile_pregridded(config)

    def test_missing_source_file_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        config = PregriddedCompilationConfig(
            source_path=tmp_path / "does_not_exist.parquet",
            features=(
                PregriddedFeatureSpec(
                    "ghsbuilts_built_area", "built_area",
                ),
            ),
        )
        with pytest.raises(FileNotFoundError):
            compile_pregridded(config)
