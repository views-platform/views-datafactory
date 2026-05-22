"""Tests for GHS-BUILT-S viewpoint v1 — spatial aggregation + temporal interpolation.

Green: happy path (config, aggregation, interpolation, full flow, provenance).
Beige: boundary conditions (zero cells, missing source dir).
Red: failure handling (missing epochs, invalid config).

Ref: ADR-034 (GHS-BUILT-S source), ADR-030 (tifffile tooling), ADR-014 (viewpoints).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

# ---------------------------------------------------------------------------
# Helpers — synthetic raster creation
# ---------------------------------------------------------------------------


def _make_synthetic_geotiff(
    path: Path,
    data: np.ndarray,
) -> Path:
    """Write a synthetic GeoTIFF via tifffile with WGS84 GeoKey tags.

    GHS-BUILT-S uses uint32 with no nodata sentinel — zero means
    no built-up surface.
    """
    import tifffile

    nrow, ncol = data.shape
    assert nrow % 60 == 0 and ncol % 60 == 0, (
        f"Raster dims ({nrow}, {ncol}) must be divisible by 60"
    )

    pixel_scale_deg = 1.0 / 120.0  # 30 arcsec

    tiepoint = (0.0, 0.0, 0.0, -180.0, 90.0, 0.0)
    pixel_scale = (pixel_scale_deg, pixel_scale_deg, 0.0)

    geokeys = (
        1, 1, 0, 2,
        1024, 0, 1, 2,
        2048, 0, 1, 4326,
    )

    extra_tags = [
        (33922, "d", len(tiepoint), tiepoint),
        (33550, "d", len(pixel_scale), pixel_scale),
        (34735, "H", len(geokeys), geokeys),
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(
        str(path),
        data.astype(np.uint32),
        extratags=extra_tags,
    )
    return path


def _make_uniform_raster(
    path: Path,
    value: int,
    *,
    prio_rows: int = 2,
    prio_cols: int = 2,
) -> Path:
    nrow = prio_rows * 60
    ncol = prio_cols * 60
    data = np.full((nrow, ncol), value, dtype=np.uint32)
    return _make_synthetic_geotiff(path, data)


# ===================================================================
# GREEN — Config
# ===================================================================


class TestGhsBuiltSViewpointConfigGreen:
    """Config defaults and immutability."""

    def test_defaults(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(
            source_dir=Path("data/raw/ghsbuilts"),
        )
        assert cfg.source_dir == Path("data/raw/ghsbuilts")
        assert cfg.aggregation == "sum"
        assert cfg.temporal_interpolation == "linear"
        assert cfg.version == "ghsbuilts_v1"

    def test_frozen(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(
            source_dir=Path("data/raw/ghsbuilts"),
        )
        with pytest.raises(AttributeError):
            cfg.version = "v2"  # type: ignore[misc]

    def test_tif_filename(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(
            source_dir=Path("data/raw/ghsbuilts"),
        )
        assert cfg.tif_filename(2020) == (
            "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
        )

    def test_no_args_raises(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        with pytest.raises(ValueError, match="Either"):
            build_ghsbuilts_v1()


# ===================================================================
# GREEN — Aggregation
# ===================================================================


class TestAggregationGreen:
    """Spatial aggregation with strip processing."""

    def test_uniform_raster_sums_correctly(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        p = 60
        data = np.ones((p * 2, p * 2), dtype=np.uint32) * 100
        grid = _aggregate_with_alignment(data, 0, 0)

        assert grid.shape == (360, 720)
        assert grid[0, 0] == 100 * p * p
        assert grid[0, 1] == 100 * p * p
        assert grid[1, 0] == 100 * p * p
        assert grid[1, 1] == 100 * p * p
        assert grid[2, 0] == 0.0

    def test_zero_raster_produces_zeros(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        p = 60
        data = np.zeros((p * 2, p * 2), dtype=np.uint32)
        grid = _aggregate_with_alignment(data, 0, 0)

        assert grid.sum() == 0.0

    def test_offset_alignment(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        p = 60
        data = np.ones((p, p), dtype=np.uint32) * 50
        grid = _aggregate_with_alignment(data, p, p)

        assert grid[1, 1] == 50 * p * p
        assert grid[0, 0] == 0.0
        assert grid[0, 1] == 0.0
        assert grid[1, 0] == 0.0


# ===================================================================
# GREEN — Temporal interpolation
# ===================================================================


class TestTemporalInterpolationGreen:
    """Temporal interpolation strategies."""

    def test_step_holds_value(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {2000: 100.0, 2005: 200.0},
            strategy="step",
            start_year=2000,
            start_month=1,
            end_year=2005,
            end_month=12,
        )

        assert result[0] == 100.0
        assert result[59] == 100.0
        assert result[60] == 200.0

    def test_linear_interpolates(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {2000: 0.0, 2010: 120.0},
            strategy="linear",
            start_year=2005,
            start_month=1,
            end_year=2005,
            end_month=1,
        )

        assert 55.0 < result[0] < 65.0

    def test_before_first_epoch_is_zero(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {2000: 100.0},
            strategy="linear",
            start_year=1990,
            start_month=1,
            end_year=1990,
            end_month=1,
        )

        assert result[0] == 0.0


# ===================================================================
# GREEN — Full flow
# ===================================================================


class TestBuildGhsBuiltSV1Green:
    """End-to-end flow with synthetic rasters."""

    def test_full_flow_two_epochs(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
            build_ghsbuilts_v1,
        )

        source_dir = tmp_path / "raw"
        source_dir.mkdir()

        _make_uniform_raster(
            source_dir
            / "GHS_BUILT_S_E2000_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=100,
        )
        _make_uniform_raster(
            source_dir
            / "GHS_BUILT_S_E2005_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=200,
        )

        config = GhsBuiltSViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "output" / "ghsbuilts_v1.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2000, 2005),
            start_year=2000,
            start_month=1,
            end_year=2005,
            end_month=12,
        )

        result = build_ghsbuilts_v1(config)

        assert result.output_path.exists()
        assert result.n_events_output > 0
        assert len(result.output_digest) == 16
        assert result.version == "ghsbuilts_v1"

        table = pq.read_table(result.output_path)
        assert "pgid" in table.column_names
        assert "month_id" in table.column_names
        assert "built_area" in table.column_names

        ledger_entries = [
            json.loads(line)
            for line in (tmp_path / "ledger.jsonl")
            .read_text()
            .strip()
            .split("\n")
        ]
        assert len(ledger_entries) == 1
        assert ledger_entries[0]["outcome"] == "success"
        assert ledger_entries[0]["dataset"] == (
            "ghsbuilts_viewpoint"
        )

    def test_lists_deleted_after_arrow_creation(
        self, tmp_path: Path,
    ) -> None:
        """Verify del is called after pa.table() — OOM lesson."""
        import ast
        import inspect

        from datafactory_viewpoint.builders import ghsbuilts_v1

        source = inspect.getsource(ghsbuilts_v1.build_ghsbuilts_v1)
        tree = ast.parse(source)

        del_targets: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Delete):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        del_targets.add(target.id)

        assert "pgid_rows" in del_targets
        assert "month_id_rows" in del_targets
        assert "built_area_rows" in del_targets

    def test_read_geotiff_limits_decompression_threads(
        self,
    ) -> None:
        """Verify maxworkers=1 in _read_geotiff — OOM lesson."""
        import inspect

        from datafactory_viewpoint.builders import ghsbuilts_v1

        source = inspect.getsource(ghsbuilts_v1._read_geotiff)
        assert "maxworkers=1" in source


# ===================================================================
# BEIGE — Edge cases
# ===================================================================


class TestGhsBuiltSViewpointBeige:
    """Boundary conditions."""

    def test_unknown_epoch_raises(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        with pytest.raises(ValueError, match="Unknown epoch"):
            GhsBuiltSViewpointConfig(
                source_dir=Path("data"),
                epochs=(1999,),
            )

    def test_invalid_interpolation_raises(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        with pytest.raises(ValueError, match="Unknown"):
            GhsBuiltSViewpointConfig(
                source_dir=Path("data"),
                temporal_interpolation="cubic",
            )

    def test_missing_source_dir_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
            build_ghsbuilts_v1,
        )

        config = GhsBuiltSViewpointConfig(
            source_dir=tmp_path / "nonexistent",
            epochs=(2020,),
        )
        with pytest.raises(FileNotFoundError):
            build_ghsbuilts_v1(config)

    def test_missing_epoch_file_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
            build_ghsbuilts_v1,
        )

        source_dir = tmp_path / "raw"
        source_dir.mkdir()

        config = GhsBuiltSViewpointConfig(
            source_dir=source_dir,
            epochs=(2020,),
        )
        with pytest.raises(FileNotFoundError, match="2020"):
            build_ghsbuilts_v1(config)

    def test_source_dir_shortcut(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        source_dir = tmp_path / "raw"
        source_dir.mkdir()

        for epoch in (
            1975, 1980, 1985, 1990, 1995,
            2000, 2005, 2010, 2015, 2020, 2025, 2030,
        ):
            _make_uniform_raster(
                source_dir
                / f"GHS_BUILT_S_E{epoch}_GLOBE_R2023A_4326_30ss_V1_0.tif",
                value=10,
                prio_rows=1,
                prio_cols=1,
            )

        result = build_ghsbuilts_v1(
            source_dir=source_dir,
        )
        assert result.output_path.exists()


# ===================================================================
# GREEN — Registry
# ===================================================================


class TestGhsBuiltSBuilderRegistryGreen:
    """Builder auto-registration."""

    def test_registered_in_builder_registry(self) -> None:
        import datafactory_viewpoint.builders.ghsbuilts_v1  # noqa: F401
        from datafactory_viewpoint.builders import list_builders

        assert "ghsbuilts_v1" in list_builders()
