"""Tests for GHS-BUILT-S viewpoint v1 — spatial aggregation + temporal interpolation.

Green: happy path (config, aggregation, interpolation, full flow, provenance).
Beige: boundary conditions (zero cells, missing source dir).
Red: failure handling (uint32 overflow, invalid config, missing tags).

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
    *,
    include_geo_tags: bool = True,
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

    extra_tags: list[tuple[int, str, int, tuple[float, ...]]] = []

    if include_geo_tags:
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


def _two_epoch_config(
    tmp_path: Path,
    value_a: int = 100,
    value_b: int = 200,
    *,
    epochs: tuple[int, int] = (2000, 2005),
    temporal_interpolation: str = "linear",
    prio_rows: int = 2,
    prio_cols: int = 2,
):
    """Create a two-epoch test scenario and return (config, source_dir)."""
    from datafactory_viewpoint.builders.ghsbuilts_v1 import (
        GhsBuiltSViewpointConfig,
    )

    source_dir = tmp_path / "raw"
    source_dir.mkdir()

    _make_uniform_raster(
        source_dir
        / f"GHS_BUILT_S_E{epochs[0]}_GLOBE_R2023A_4326_30ss_V1_0.tif",
        value=value_a,
        prio_rows=prio_rows,
        prio_cols=prio_cols,
    )
    _make_uniform_raster(
        source_dir
        / f"GHS_BUILT_S_E{epochs[1]}_GLOBE_R2023A_4326_30ss_V1_0.tif",
        value=value_b,
        prio_rows=prio_rows,
        prio_cols=prio_cols,
    )

    config = GhsBuiltSViewpointConfig(
        source_dir=source_dir,
        output_path=tmp_path / "output" / "ghsbuilts_v1.parquet",
        ledger_path=tmp_path / "ledger.jsonl",
        epochs=epochs,
        start_year=epochs[0],
        start_month=1,
        end_year=epochs[1],
        end_month=12,
        temporal_interpolation=temporal_interpolation,
    )
    return config, source_dir


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

    def test_all_known_epochs_accepted(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            KNOWN_EPOCHS,
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(
            source_dir=Path("data"),
            epochs=KNOWN_EPOCHS,
        )
        assert cfg.epochs == KNOWN_EPOCHS
        assert len(cfg.epochs) == 12


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

    def test_result_dtype_is_float64(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        data = np.ones((60, 60), dtype=np.uint32)
        grid = _aggregate_with_alignment(data, 0, 0)

        assert grid.dtype == np.float64

    def test_nonuniform_raster_sums_per_cell(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        p = 60
        data = np.zeros((p, p * 2), dtype=np.uint32)
        data[:, :p] = 10
        data[:, p:] = 20
        grid = _aggregate_with_alignment(data, 0, 0)

        assert grid[0, 0] == 10 * p * p
        assert grid[0, 1] == 20 * p * p


# ===================================================================
# GREEN — Temporal interpolation
# ===================================================================


class TestTemporalInterpolationGreen:
    """Temporal interpolation strategies."""

    def test_step_holds_value(self) -> None:
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
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
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
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
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
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

    def test_linear_monotonic_increase(self) -> None:
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {2000: 100.0, 2010: 500.0},
            strategy="linear",
            start_year=2000,
            start_month=1,
            end_year=2010,
            end_month=12,
        )

        for i in range(1, len(result)):
            assert result[i] >= result[i - 1], (
                f"Month {i}: {result[i]} < {result[i-1]}"
            )

    def test_after_last_epoch_is_flat(self) -> None:
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {2000: 100.0, 2005: 300.0},
            strategy="linear",
            start_year=2000,
            start_month=1,
            end_year=2010,
            end_month=12,
        )

        assert result[-1] == 300.0
        assert result[-12] == 300.0

    def test_step_changes_only_at_epochs(self) -> None:
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {2000: 100.0, 2005: 200.0, 2010: 300.0},
            strategy="step",
            start_year=2000,
            start_month=1,
            end_year=2010,
            end_month=12,
        )

        for i in range(1, 60):
            assert result[i] == result[0], f"Changed at month {i}"
        assert result[60] == 200.0
        assert result[61] == 200.0

    def test_many_epochs_linear_smooth(self) -> None:
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
        )

        epochs = {
            1975: 0.0, 1980: 10.0, 1985: 20.0, 1990: 30.0,
            1995: 40.0, 2000: 50.0, 2005: 60.0, 2010: 70.0,
            2015: 80.0, 2020: 90.0, 2025: 100.0, 2030: 110.0,
        }
        result = _interpolate_temporal(
            epochs,
            strategy="linear",
            start_year=1975,
            start_month=1,
            end_year=2030,
            end_month=12,
        )

        for i in range(1, len(result)):
            assert result[i] >= result[i - 1]


# ===================================================================
# GREEN — Full flow
# ===================================================================


class TestBuildGhsBuiltSV1Green:
    """End-to-end flow with synthetic rasters."""

    def test_full_flow_two_epochs(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
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
        """Verify maxworkers=1 in read_geotiff — OOM lesson."""
        import inspect

        from datafactory_viewpoint import raster_io

        source = inspect.getsource(raster_io.read_geotiff)
        assert "maxworkers=1" in source

    def test_output_schema_types(self, tmp_path: Path) -> None:
        import pyarrow as pa

        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        assert table.schema.field("pgid").type == pa.int32()
        assert table.schema.field("month_id").type == pa.int32()
        assert table.schema.field("built_area").type == pa.float64()

    def test_zero_raster_produces_empty_output(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(
            tmp_path, value_a=0, value_b=0,
        )
        result = build_ghsbuilts_v1(config)

        assert result.n_events_output == 0
        assert result.output_path.exists()

    def test_pgid_mapping_nw_corner(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(
            tmp_path, prio_rows=1, prio_cols=1,
        )
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        pgids = table.column("pgid").to_pylist()
        assert len(set(pgids)) == 1
        assert pgids[0] >= 1

    def test_month_id_views_convention(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        month_ids = sorted(set(table.column("month_id").to_pylist()))
        expected_first = (2000 - 1980) * 12 + 1  # 241
        assert month_ids[0] == expected_first

    def test_no_duplicate_pgid_month_pairs(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        pairs = list(zip(
            table.column("pgid").to_pylist(),
            table.column("month_id").to_pylist(),
            strict=True,
        ))
        assert len(pairs) == len(set(pairs))

    def test_built_area_all_nonnegative(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        values = table.column("built_area").to_pylist()
        assert all(v >= 0.0 for v in values)
        assert all(v > 0.0 for v in values)


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

    def test_from_shortcuts_source_dir(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
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

        config = GhsBuiltSViewpointConfig.from_shortcuts(
            source_dir=source_dir,
        )
        result = build_ghsbuilts_v1(config)
        assert result.output_path.exists()

    def test_single_epoch_full_flow(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
            build_ghsbuilts_v1,
        )

        source_dir = tmp_path / "raw"
        source_dir.mkdir()
        _make_uniform_raster(
            source_dir
            / "GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=500,
            prio_rows=1,
            prio_cols=1,
        )

        config = GhsBuiltSViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out" / "v.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2020,),
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=12,
        )
        result = build_ghsbuilts_v1(config)

        assert result.output_path.exists()
        assert result.n_events_output > 0

    def test_step_interpolation_full_flow(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(
            tmp_path,
            value_a=100,
            value_b=200,
            temporal_interpolation="step",
        )
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        values = table.column("built_area").to_pylist()
        unique_values = sorted(set(values))
        assert len(unique_values) == 2

    def test_large_uint32_full_flow(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(
            tmp_path,
            value_a=1_000_000,
            value_b=2_000_000,
            prio_rows=1,
            prio_cols=1,
        )
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        values = table.column("built_area").to_pylist()
        assert max(values) > 1e9


# ===================================================================
# RED — Aggregation failure modes
# ===================================================================


class TestAggregationRed:
    """Adversarial inputs to spatial aggregation."""

    def test_uint32_large_values_no_overflow(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        p = 60
        max_val = np.iinfo(np.uint32).max
        data = np.full((p, p), max_val, dtype=np.uint32)
        grid = _aggregate_with_alignment(data, 0, 0)

        expected = float(max_val) * p * p
        assert grid[0, 0] == pytest.approx(expected, rel=1e-10)
        assert grid.dtype == np.float64

    def test_negative_offset_clips(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        p = 60
        data = np.ones((p, p * 2), dtype=np.uint32) * 100
        grid = _aggregate_with_alignment(data, 0, -30)

        full_cell = 100 * p * p
        assert grid[0, 0] == full_cell

    def test_offset_beyond_globe_zeros(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GLOBE_PIXEL_ROWS,
            _aggregate_with_alignment,
        )

        p = 60
        data = np.ones((p, p), dtype=np.uint32) * 999
        grid = _aggregate_with_alignment(
            data, GLOBE_PIXEL_ROWS + 100, 0,
        )

        assert grid.sum() == 0.0

    def test_partial_row_coverage(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        data = np.ones((30, 60), dtype=np.uint32) * 100
        grid = _aggregate_with_alignment(data, 0, 0)

        assert grid[0, 0] == 100 * 30 * 60

    def test_single_pixel_placement(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        p = 60
        data = np.zeros((p * 2, p * 2), dtype=np.uint32)
        data[p + 10, p + 10] = 42
        grid = _aggregate_with_alignment(data, 0, 0)

        assert grid[1, 1] == 42.0
        nonzero_cells = np.count_nonzero(grid)
        assert nonzero_cells == 1


# ===================================================================
# RED — Temporal interpolation failure modes
# ===================================================================


class TestTemporalInterpolationRed:
    """Adversarial inputs to temporal interpolation."""

    def test_empty_epoch_values_returns_zeros(self) -> None:
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {},
            strategy="linear",
            start_year=2000,
            start_month=1,
            end_year=2000,
            end_month=12,
        )

        assert len(result) == 12
        assert all(v == 0.0 for v in result)

    def test_single_epoch_linear_flat_after(self) -> None:
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {2000: 500.0},
            strategy="linear",
            start_year=1995,
            start_month=1,
            end_year=2005,
            end_month=12,
        )

        for v in result[:60]:
            assert v == 0.0
        for v in result[60:]:
            assert v == 500.0

    def test_single_epoch_step_flat_after(self) -> None:
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {2000: 500.0},
            strategy="step",
            start_year=1995,
            start_month=1,
            end_year=2005,
            end_month=12,
        )

        for v in result[:60]:
            assert v == 0.0
        for v in result[60:]:
            assert v == 500.0

    def test_invalid_strategy_raises(self) -> None:
        from datafactory_viewpoint.temporal import (
            interpolate_temporal as _interpolate_temporal,
        )

        with pytest.raises(ValueError, match="Unknown"):
            _interpolate_temporal(
                {2000: 100.0},
                strategy="cubic",
                start_year=2000,
                start_month=1,
                end_year=2000,
                end_month=12,
            )


# ===================================================================
# RED — Build function failure modes
# ===================================================================


class TestBuildGhsBuiltSV1Red:
    """Adversarial config and input handling."""

    def test_empty_version_raises(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        with pytest.raises(ValueError, match="version"):
            GhsBuiltSViewpointConfig(
                source_dir=Path("data"),
                version="",
            )

    def test_empty_epochs_raises(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        with pytest.raises(ValueError, match="epoch"):
            GhsBuiltSViewpointConfig(
                source_dir=Path("data"),
                epochs=(),
            )

    def test_geotiff_missing_tags_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.raster_io import read_geotiff

        p = 60
        data = np.ones((p, p), dtype=np.uint32)
        path = _make_synthetic_geotiff(
            tmp_path / "no_tags.tif",
            data,
            include_geo_tags=False,
        )

        with pytest.raises(ValueError, match="geotransform"):
            read_geotiff(path)

    def test_no_args_raises(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        with pytest.raises(TypeError):
            build_ghsbuilts_v1()  # type: ignore[call-arg]


# ===================================================================
# GREEN — Config details (#284, C-189)
# ===================================================================


class TestGhsBuiltSViewpointConfigDetailsGreen:
    """Config field defaults and methods."""

    def test_default_version(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        assert cfg.version == "ghsbuilts_v1"

    def test_default_temporal_interpolation(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        assert cfg.temporal_interpolation == "linear"

    def test_default_aggregation(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        assert cfg.aggregation == "sum"

    def test_default_start_year(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        assert cfg.start_year == 1975

    def test_default_end_year(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        assert cfg.end_year == 2030

    def test_default_resolution(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        assert cfg.resolution == "30ss"

    def test_default_crs(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        assert cfg.crs == "4326"

    def test_tif_filename_per_epoch(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        for epoch in cfg.epochs:
            name = cfg.tif_filename(epoch)
            assert f"E{epoch}" in name
            assert name.endswith(".tif")

    def test_from_shortcuts_returns_config(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig.from_shortcuts(
            source_dir=Path("/tmp"),
        )
        assert isinstance(cfg, GhsBuiltSViewpointConfig)
        assert cfg.source_dir == Path("/tmp")


# ===================================================================
# GREEN — Aggregation conservation (#284, C-189)
# ===================================================================


class TestAggregationConservationGreen:
    """Sum conservation: input pixel sum = output cell sum."""

    def test_sum_conservation_uniform(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        raster = np.full((120, 120), 1, dtype=np.uint32)
        result = _aggregate_with_alignment(raster, 0, 0)
        expected = 60 * 60
        assert result[0, 0] == expected
        assert result[1, 1] == expected

    def test_sum_conservation_nonuniform(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        rng = np.random.default_rng(42)
        raster = rng.integers(0, 1000, (120, 120), dtype=np.uint32)
        result = _aggregate_with_alignment(raster, 0, 0)
        assert np.isclose(result.sum(), raster.astype(np.float64).sum())

    def test_sum_conservation_large_values(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        raster = np.full((60, 60), 2**30, dtype=np.uint32)
        result = _aggregate_with_alignment(raster, 0, 0)
        assert result[0, 0] == float(2**30) * 60 * 60


# ===================================================================
# GREEN — Build output schema (#284, C-189)
# ===================================================================


class TestBuildOutputSchemaGreen:
    """Output Parquet has expected columns and types."""

    def test_output_columns_are_pgid_month_built(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        build_ghsbuilts_v1(config)

        table = pq.read_table(config.output_path)
        assert set(table.column_names) == {
            "pgid", "month_id", "built_area",
        }

    def test_pgid_is_int32(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        build_ghsbuilts_v1(config)

        schema = pq.read_schema(config.output_path)
        assert schema.field("pgid").type == "int32"

    def test_month_id_is_int32(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        build_ghsbuilts_v1(config)

        schema = pq.read_schema(config.output_path)
        assert schema.field("month_id").type == "int32"

    def test_built_area_is_float64(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        build_ghsbuilts_v1(config)

        schema = pq.read_schema(config.output_path)
        assert schema.field("built_area").type == "double"

    def test_built_area_all_nonneg_in_output(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        build_ghsbuilts_v1(config)

        table = pq.read_table(config.output_path)
        areas = table.column("built_area").to_numpy()
        assert np.all(areas >= 0)

    def test_provenance_has_output_digest(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        build_ghsbuilts_v1(config)

        entry = json.loads(
            config.ledger_path.read_text().strip().splitlines()[-1]
        )
        assert "output_digest" in entry
        assert len(entry["output_digest"]) == 16

    def test_provenance_has_n_cells(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        build_ghsbuilts_v1(config)

        entry = json.loads(
            config.ledger_path.read_text().strip().splitlines()[-1]
        )
        assert "n_cells_output" in entry
        assert entry["n_cells_output"] > 0


# ===================================================================
# BEIGE — Config boundaries (#284, C-189)
# ===================================================================


class TestGhsBuiltSViewpointConfigBeigeExtra:
    """Additional boundary conditions."""

    def test_single_epoch_config_accepted(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(
            source_dir=Path("/tmp"),
            epochs=(2020,),
        )
        assert cfg.epochs == (2020,)

    def test_first_known_epoch_only(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(
            source_dir=Path("/tmp"),
            epochs=(1975,),
        )
        assert cfg.epochs == (1975,)

    def test_last_known_epoch_only(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(
            source_dir=Path("/tmp"),
            epochs=(2030,),
        )
        assert cfg.epochs == (2030,)

    def test_custom_start_end_years(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(
            source_dir=Path("/tmp"),
            start_year=2000,
            end_year=2020,
        )
        assert cfg.start_year == 2000
        assert cfg.end_year == 2020


# ===================================================================
# RED — Aggregation adversarial (#284, C-189)
# ===================================================================


class TestAggregationAdversarialRed:
    """Additional adversarial cases for spatial aggregation."""

    def test_zero_raster_produces_all_zeros(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        raster = np.zeros((120, 120), dtype=np.uint32)
        result = _aggregate_with_alignment(raster, 0, 0)
        assert np.all(result == 0)

    def test_max_uint32_no_float64_overflow(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        raster = np.full((60, 60), np.iinfo(np.uint32).max, dtype=np.uint32)
        result = _aggregate_with_alignment(raster, 0, 0)
        assert np.isfinite(result[0, 0])
        assert result[0, 0] > 0


class TestBuildAdversarialRed:
    """Additional adversarial cases for the builder."""

    def test_frozen_config_rejects_mutation(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        with pytest.raises(AttributeError):
            cfg.version = "hacked"  # type: ignore[misc]

    def test_frozen_config_source_dir_mutation(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(source_dir=Path("/tmp"))
        with pytest.raises(AttributeError):
            cfg.source_dir = Path("/evil")  # type: ignore[misc]


# ===================================================================
# GREEN — ViewpointResult structure (#284, C-189)
# ===================================================================


class TestViewpointResultGreen:
    """ViewpointResult fields populated correctly."""

    def test_result_has_output_path(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        assert result.output_path == config.output_path
        assert result.output_path.exists()

    def test_result_has_version(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        assert result.version == "ghsbuilts_v1"

    def test_result_n_events_input_positive(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        assert result.n_events_input > 0

    def test_result_output_digest_16_hex(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        assert len(result.output_digest) == 16
        assert all(c in "0123456789abcdef" for c in result.output_digest)

    def test_result_n_filtered_is_zero(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        assert result.n_filtered == 0

    def test_result_n_summary_expanded_is_zero(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        assert result.n_summary_expanded == 0


# ===================================================================
# GREEN — Provenance ledger details (#284, C-189)
# ===================================================================


class TestViewpointProvenanceGreen:
    """Ledger entry structure and completeness."""

    def test_provenance_has_all_fields(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        build_ghsbuilts_v1(config)

        entry = json.loads(
            config.ledger_path.read_text().strip().splitlines()[-1]
        )
        assert entry["dataset"] == "ghsbuilts_viewpoint"
        assert entry["version"] == "ghsbuilts_v1"
        assert entry["outcome"] == "success"
        assert "output_digest" in entry
        assert "n_cells_output" in entry
        assert "n_epochs" in entry
        assert entry["n_epochs"] == 2
        assert entry["temporal_interpolation"] == "linear"
        assert entry["aggregation"] == "sum"
        assert "ledger_version" in entry
        assert "digest_algorithm" in entry
        assert "sha256" in entry["digest_algorithm"]
        assert entry["ledger_version"] >= 1


# ===================================================================
# GREEN — Registry
# ===================================================================


class TestGhsBuiltSBuilderRegistryGreen:
    """Builder auto-registration."""

    def test_registered_in_builder_registry(self) -> None:
        import datafactory_viewpoint.builders.ghsbuilts_v1  # noqa: F401
        from datafactory_viewpoint.builders import list_builders

        assert "ghsbuilts_v1" in list_builders()
