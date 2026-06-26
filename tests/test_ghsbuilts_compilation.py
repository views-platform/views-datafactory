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


# ===================================================================
# GREEN — Config details (#284, C-189)
# ===================================================================


class TestPregriddedCompilationConfigDetailsGreen:
    """Config default values and feature spec."""

    def test_default_fill_value(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(PregriddedFeatureSpec("a", "a"),),
        )
        assert config.fill_value == 0.0

    def test_default_output_dtype(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(PregriddedFeatureSpec("a", "a"),),
        )
        assert config.output_dtype == "float32"

    def test_default_pgid_field(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(PregriddedFeatureSpec("a", "a"),),
        )
        assert config.pgid_field == "pgid"

    def test_default_month_id_field(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(PregriddedFeatureSpec("a", "a"),),
        )
        assert config.month_id_field == "month_id"

    def test_feature_spec_accessible(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedFeatureSpec,
        )

        spec = PregriddedFeatureSpec("ghsbuilts_built_area", "built_area")
        assert spec.name == "ghsbuilts_built_area"
        assert spec.value_field == "built_area"

    def test_frozen_config_rejects_mutation(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(PregriddedFeatureSpec("a", "a"),),
        )
        with pytest.raises(AttributeError):
            config.fill_value = 999.0  # type: ignore[misc]


# ===================================================================
# GREEN — Compile behavior (#284, C-189)
# ===================================================================


class TestCompilePregriddedBehaviorGreen:
    """Additional green-path behavior tests."""

    def test_nan_values_skipped(self, tmp_path: Path) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1, 1],
            month_ids=[1, 2],
            built_areas=[100.0, float("nan")],
        )
        assert grid[0, 0, 0, 0] == pytest.approx(100.0, rel=1e-5)
        assert grid[1, 0, 0, 0] == 0.0

    def test_multiple_cells_different_months(
        self, tmp_path: Path,
    ) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1, 2, 3],
            month_ids=[1, 1, 2],
            built_areas=[10.0, 20.0, 30.0],
        )
        assert grid[0, 0, 0, 0] == pytest.approx(10.0, rel=1e-5)

    def test_output_dir_created(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "deep" / "nested" / "compiled"
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "source.parquet"
        _make_ghsbuilts_parquet(source, [1], [1], [100.0])

        config = PregriddedCompilationConfig(
            source_path=source,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                start_year=1980, start_month=1,
                end_year=1980, end_month=12,
            ),
            features=(
                PregriddedFeatureSpec(
                    "ghsbuilts_built_area", "built_area",
                ),
            ),
            output_dir=out_dir,
            ledger_path=tmp_path / "ledger.jsonl",
        )
        compile_pregridded(config)
        assert out_dir.exists()

    def test_grid_shape_is_thwc(self, tmp_path: Path) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[50.0],
        )
        assert len(grid.shape) == 4
        assert grid.shape[3] == 1

    def test_provenance_json_written(self, tmp_path: Path) -> None:
        out_dir, _ = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[50.0],
        )
        prov = out_dir / "provenance.json"
        assert prov.exists()
        data = json.loads(prov.read_text())
        assert "source_digest" in data


# ===================================================================
# BEIGE — Config boundaries (#284, C-189)
# ===================================================================


class TestPregriddedConfigBeigeExtra:
    """Additional config boundary tests."""

    def test_float64_dtype_accepted(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(PregriddedFeatureSpec("a", "a"),),
            output_dtype="float64",
        )
        assert config.output_dtype == "float64"

    def test_int32_dtype_accepted(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(PregriddedFeatureSpec("a", "a"),),
            output_dtype="int32",
        )
        assert config.output_dtype == "int32"

    def test_float16_dtype_accepted(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(PregriddedFeatureSpec("a", "a"),),
            output_dtype="float16",
        )
        assert config.output_dtype == "float16"

    def test_multiple_features_accepted(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(
                PregriddedFeatureSpec("feat_a", "col_a"),
                PregriddedFeatureSpec("feat_b", "col_b"),
            ),
        )
        assert len(config.features) == 2

    def test_custom_fill_value(self, tmp_path: Path) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[],
            month_ids=[],
            built_areas=[],
            fill_value=-1.0,
        )
        assert grid[0, 0, 0, 0] == pytest.approx(-1.0, rel=1e-5)


# ===================================================================
# RED — Config adversarial (#284, C-189)
# ===================================================================


class TestPregriddedConfigRed:
    """Config adversarial: invalid dtypes, duplicate features."""

    def test_invalid_dtype_raises(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        with pytest.raises(ValueError, match="output_dtype"):
            PregriddedCompilationConfig(
                source_path=Path("/tmp/test.parquet"),
                features=(PregriddedFeatureSpec("a", "a"),),
                output_dtype="bfloat16",
            )

    def test_empty_features_raises(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
        )

        with pytest.raises(ValueError, match="features"):
            PregriddedCompilationConfig(
                source_path=Path("/tmp/test.parquet"),
                features=(),
            )

    def test_duplicate_feature_names_raises(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        with pytest.raises(ValueError, match="duplicate"):
            PregriddedCompilationConfig(
                source_path=Path("/tmp/test.parquet"),
                features=(
                    PregriddedFeatureSpec("dup", "col_a"),
                    PregriddedFeatureSpec("dup", "col_b"),
                ),
            )

    def test_config_mutation_rejected(self) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
        )

        config = PregriddedCompilationConfig(
            source_path=Path("/tmp/test.parquet"),
            features=(PregriddedFeatureSpec("a", "a"),),
        )
        with pytest.raises(AttributeError):
            config.source_path = Path("/evil")  # type: ignore[misc]


# ===================================================================
# GREEN — Sidecar file integrity (#284, C-189)
# ===================================================================


class TestCompileSidecarFilesGreen:
    """Verify all sidecar files are written correctly."""

    def test_feature_names_json_content(
        self, tmp_path: Path,
    ) -> None:
        out_dir, _ = _compile_ghsbuilts(
            tmp_path,
            pgids=[1, 2],
            month_ids=[1, 1],
            built_areas=[100.0, 200.0],
        )
        names_path = out_dir / "feature_names.json"
        assert names_path.exists()
        names = json.loads(names_path.read_text())
        assert names == ["ghsbuilts_built_area"]

    def test_time_steps_npy_shape(self, tmp_path: Path) -> None:
        out_dir, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[50.0],
        )
        ts = np.load(out_dir / "time_steps.npy")
        assert ts.shape[0] == grid.shape[0]

    def test_pgids_npy_shape(self, tmp_path: Path) -> None:
        out_dir, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[50.0],
        )
        pgids = np.load(out_dir / "pgids.npy")
        assert pgids.shape == (grid.shape[1], grid.shape[2])

    def test_grid_npy_dtype_is_float32(
        self, tmp_path: Path,
    ) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[50.0],
        )
        assert grid.dtype == np.float32

    def test_ledger_has_n_placed(
        self, tmp_path: Path,
    ) -> None:
        _compile_ghsbuilts(
            tmp_path,
            pgids=[1, 2],
            month_ids=[1, 1],
            built_areas=[100.0, 200.0],
        )
        ledger = tmp_path / "ledger.jsonl"
        entry = json.loads(ledger.read_text().strip().splitlines()[-1])
        assert entry["n_placed"] == 2
        assert entry["n_skipped_spatial"] == 0
        assert entry["n_skipped_temporal"] == 0

    def test_provenance_source_digest_is_16_hex(
        self, tmp_path: Path,
    ) -> None:
        out_dir, _ = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[50.0],
        )
        prov = json.loads((out_dir / "provenance.json").read_text())
        digest = prov["source_digest"]
        assert len(digest) == 16
        assert all(c in "0123456789abcdef" for c in digest)

    def test_ledger_entry_written(self, tmp_path: Path) -> None:
        _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[50.0],
        )
        ledger = tmp_path / "ledger.jsonl"
        assert ledger.exists()
        entry = json.loads(ledger.read_text().strip().splitlines()[-1])
        assert entry["dataset"] == "pregridded_compilation"
        assert "output_digest" in entry


# ===================================================================
# GREEN — Spatial placement math (#284, C-189)
# ===================================================================


class TestSpatialPlacementGreen:
    """Verify pgid → (row, col) mapping in compilation."""

    def test_pgid_1_is_bottom_left(self, tmp_path: Path) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1],
            month_ids=[1],
            built_areas=[42.0],
        )
        assert grid[0, 0, 0, 0] == pytest.approx(42.0, rel=1e-5)

    def test_pgid_720_is_first_row_last_col(
        self, tmp_path: Path,
    ) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[720],
            month_ids=[1],
            built_areas=[99.0],
        )
        assert grid[0, 0, 719, 0] == pytest.approx(99.0, rel=1e-5)

    def test_pgid_721_is_second_row_first_col(
        self, tmp_path: Path,
    ) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[721],
            month_ids=[1],
            built_areas=[77.0],
        )
        assert grid[0, 1, 0, 0] == pytest.approx(77.0, rel=1e-5)

    def test_values_placed_at_correct_time_index(
        self, tmp_path: Path,
    ) -> None:
        _, grid = _compile_ghsbuilts(
            tmp_path,
            pgids=[1, 1],
            month_ids=[1, 6],
            built_areas=[10.0, 60.0],
        )
        assert grid[0, 0, 0, 0] == pytest.approx(10.0, rel=1e-5)
        assert grid[5, 0, 0, 0] == pytest.approx(60.0, rel=1e-5)
        assert grid[3, 0, 0, 0] == 0.0
