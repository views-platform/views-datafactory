"""Tests for GHS-BUILT-S compilation via pregridded compilation.

Green: happy path (config, placement, provenance).
Beige: boundary conditions (out-of-bounds, empty data).

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


# ===================================================================
# GREEN — Compilation
# ===================================================================


class TestGhsBuiltSCompilationGreen:
    """Happy-path compilation placing built_area into grid."""

    def test_places_built_area_correctly(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "ghsbuilts_v1.parquet"
        _make_ghsbuilts_parquet(
            source,
            pgids=[1, 1, 720],
            month_ids=[1, 2, 1],
            built_areas=[500.0, 750.0, 1000.0],
        )

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
            ledger_path=tmp_path / "ledger.jsonl",
        )

        output_dir = compile_pregridded(config)

        grid = np.load(output_dir / "grid.npy")
        assert grid.shape == (12, 360, 720, 1)

        # pgid=1 → row=0, col=0; month_id=1 → time_idx=0
        assert grid[0, 0, 0, 0] == pytest.approx(500.0, rel=1e-3)
        assert grid[1, 0, 0, 0] == pytest.approx(750.0, rel=1e-3)

        # pgid=720 → row=0, col=719
        assert grid[0, 0, 719, 0] == pytest.approx(
            1000.0, rel=1e-3,
        )

        features = json.loads(
            (output_dir / "feature_names.json").read_text()
        )
        assert features == ["ghsbuilts_built_area"]

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "ghsbuilts_v1.parquet"
        _make_ghsbuilts_parquet(
            source,
            pgids=[1],
            month_ids=[1],
            built_areas=[100.0],
        )

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
            ledger_path=tmp_path / "ledger.jsonl",
        )

        output_dir = compile_pregridded(config)

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


# ===================================================================
# BEIGE — Edge cases
# ===================================================================


class TestGhsBuiltSCompilationBeige:
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

        source = tmp_path / "ghsbuilts_v1.parquet"
        _make_ghsbuilts_parquet(
            source,
            pgids=[0, 999999],
            month_ids=[1, 1],
            built_areas=[100.0, 200.0],
        )

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
            ledger_path=tmp_path / "ledger.jsonl",
        )

        output_dir = compile_pregridded(config)
        grid = np.load(output_dir / "grid.npy")

        assert grid.sum() == 0.0

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )

        config = PregriddedCompilationConfig(
            source_path=tmp_path / "nonexistent.parquet",
            features=(
                PregriddedFeatureSpec(
                    "ghsbuilts_built_area", "built_area",
                ),
            ),
        )
        with pytest.raises(FileNotFoundError):
            compile_pregridded(config)

    def test_zero_built_area_placed_correctly(
        self, tmp_path: Path,
    ) -> None:
        """Zero is a legitimate value for built-up area, not nodata."""
        from datafactory_compilation.pregridded_compilation import (
            PregriddedCompilationConfig,
            PregriddedFeatureSpec,
            compile_pregridded,
        )
        from datafactory_priogrid import GridConfig, TemporalConfig

        source = tmp_path / "ghsbuilts_v1.parquet"
        _make_ghsbuilts_parquet(
            source,
            pgids=[1],
            month_ids=[1],
            built_areas=[0.0],
        )

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
            ledger_path=tmp_path / "ledger.jsonl",
            fill_value=0.0,
        )

        output_dir = compile_pregridded(config)
        grid = np.load(output_dir / "grid.npy")

        assert grid[0, 0, 0, 0] == 0.0
