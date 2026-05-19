"""Tests for GHS-POP viewpoint v1 — spatial aggregation + temporal interpolation.

Green: happy path (config, aggregation, interpolation, full flow, provenance).
Beige: boundary conditions (nodata, ocean, missing source dir).
Red: failure handling (negative population, wrong CRS).

Ref: ADR-029 (GHS-POP source), ADR-030 (tifffile tooling), ADR-014 (viewpoints).
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

NODATA = -200.0


def _make_synthetic_geotiff(
    path: Path,
    data: np.ndarray,
    *,
    nodata: float = NODATA,
) -> Path:
    """Write a synthetic GeoTIFF via tifffile with WGS84 GeoKey tags.

    Args:
        path: Output file path.
        data: 2-D float32 array (nrow, ncol). Must be divisible by 60
              in both dimensions to align with 30ss → 0.5° aggregation.
        nodata: Fill value for missing data.

    The GeoTIFF is written with ModelTiepointTag and ModelPixelScaleTag
    matching the WGS84 30-arcsecond grid, plus GeoKey metadata marking
    EPSG:4326.
    """
    import tifffile

    nrow, ncol = data.shape
    assert nrow % 60 == 0 and ncol % 60 == 0, (
        f"Raster dims ({nrow}, {ncol}) must be divisible by 60"
    )

    pixel_scale_deg = 1.0 / 120.0  # 30 arcsec = 1/120 degree

    # ModelTiepointTag: raster (0,0) → geographic (west, north)
    # Full globe: west=-180, north=90
    tiepoint = (0.0, 0.0, 0.0, -180.0, 90.0, 0.0)
    pixel_scale = (pixel_scale_deg, pixel_scale_deg, 0.0)

    # GeoKey directory for EPSG:4326 (WGS84 geographic)
    # Format: (key_directory_version, key_revision, minor_revision, n_keys,
    #          key_id, tiff_tag_location, count, value_offset, ...)
    geokeys = (
        1, 1, 0, 2,
        # GTModelTypeGeoKey = 2 (ModelTypeGeographic)
        1024, 0, 1, 2,
        # GeographicTypeGeoKey = 4326
        2048, 0, 1, 4326,
    )

    extra_tags = [
        # ModelTiepointTag (33922)
        (33922, "d", len(tiepoint), tiepoint),
        # ModelPixelScaleTag (33550)
        (33550, "d", len(pixel_scale), pixel_scale),
        # GeoKeyDirectoryTag (34735)
        (34735, "H", len(geokeys), geokeys),
        # GDAL nodata tag (42113) — string representation
        (42113, "s", 0, str(nodata)),
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(
        str(path),
        data.astype(np.float32),
        extratags=extra_tags,
    )
    return path


def _make_uniform_raster(
    path: Path,
    value: float,
    *,
    prio_rows: int = 2,
    prio_cols: int = 2,
) -> Path:
    """Create a raster where every pixel has the same value.

    The raster dimensions are prio_rows*60 x prio_cols*60.
    """
    nrow = prio_rows * 60
    ncol = prio_cols * 60
    data = np.full((nrow, ncol), value, dtype=np.float32)
    return _make_synthetic_geotiff(path, data)


# ===================================================================
# GREEN — Config
# ===================================================================


class TestGhsPopViewpointConfigGreen:
    """Config defaults and immutability."""

    def test_defaults(self) -> None:
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
        )

        cfg = GhsPopViewpointConfig(source_dir=Path("data/raw/ghspop"))
        assert cfg.source_dir == Path("data/raw/ghspop")
        assert cfg.output_path == Path("data/viewpoint/ghspop_v1.parquet")
        assert cfg.ledger_path == Path(
            "provenance/viewpoint/ghspop_v1_ledger.jsonl"
        )
        assert cfg.version == "ghspop_v1"
        assert cfg.epochs == (
            1975, 1980, 1985, 1990, 1995,
            2000, 2005, 2010, 2015, 2020, 2025, 2030,
        )
        assert cfg.aggregation == "sum"
        assert cfg.temporal_interpolation == "step"

    def test_frozen(self) -> None:
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
        )

        cfg = GhsPopViewpointConfig(source_dir=Path("x"))
        with pytest.raises(AttributeError):
            cfg.version = "modified"  # type: ignore[misc]

    def test_custom_epochs(self) -> None:
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=Path("x"),
            epochs=(2020,),
        )
        assert cfg.epochs == (2020,)

    def test_rejects_empty_version(self) -> None:
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
        )

        with pytest.raises(ValueError, match="version"):
            GhsPopViewpointConfig(source_dir=Path("x"), version="")


# ===================================================================
# GREEN — Spatial aggregation
# ===================================================================


class TestSpatialAggregationGreen:
    """Spatial aggregation: 30ss → 0.5° via reshape + sum."""

    def test_aggregate_uniform_raster(self, tmp_path: Path) -> None:
        """Uniform raster: each PRIO-GRID cell = 60*60*value."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _aggregate_to_prio_grid,
        )

        nrow, ncol = 120, 120  # 2x2 PRIO-GRID cells
        data = np.ones((nrow, ncol), dtype=np.float32) * 5.0
        result = _aggregate_to_prio_grid(data)

        assert result.shape == (2, 2)
        expected = 60 * 60 * 5.0
        np.testing.assert_allclose(result, expected)

    def test_population_sum_conserved(self, tmp_path: Path) -> None:
        """Total population across all cells equals total input pixels."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _aggregate_to_prio_grid,
        )

        rng = np.random.default_rng(42)
        data = rng.uniform(0, 100, size=(180, 240)).astype(np.float32)
        result = _aggregate_to_prio_grid(data)

        np.testing.assert_allclose(
            result.sum(), data.sum(), rtol=1e-5,
        )

    def test_distinct_cells(self, tmp_path: Path) -> None:
        """Different values in different PRIO-GRID cells aggregate correctly."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _aggregate_to_prio_grid,
        )

        # 2x2 PRIO-GRID cells; top-left gets 10, others get 1
        data = np.ones((120, 120), dtype=np.float32)
        data[:60, :60] = 10.0
        result = _aggregate_to_prio_grid(data)

        assert result[0, 0] == 60 * 60 * 10.0
        assert result[0, 1] == 60 * 60 * 1.0
        assert result[1, 0] == 60 * 60 * 1.0
        assert result[1, 1] == 60 * 60 * 1.0


# ===================================================================
# GREEN — Temporal interpolation
# ===================================================================


class TestTemporalInterpolationGreen:
    """Step function: hold last known epoch value forward."""

    def test_step_function_basic(self) -> None:
        """Values hold until next epoch."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _interpolate_temporal,
        )

        epoch_values = {2000: 100.0, 2005: 200.0}
        months = _interpolate_temporal(
            epoch_values,
            start_year=2000,
            start_month=1,
            end_year=2005,
            end_month=12,
        )

        # Jan 2000 → Dec 2004 = 60 months at 100.0
        assert months[0] == 100.0
        assert months[59] == 100.0

        # Jan 2005 → Dec 2005 = 12 months at 200.0
        assert months[60] == 200.0
        assert months[71] == 200.0

        assert len(months) == 72

    def test_step_function_single_epoch(self) -> None:
        """Single epoch fills entire range."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _interpolate_temporal,
        )

        epoch_values = {2020: 500.0}
        months = _interpolate_temporal(
            epoch_values,
            start_year=2019,
            start_month=1,
            end_year=2021,
            end_month=12,
        )

        # Before epoch: 0 (no data yet)
        assert months[0] == 0.0  # Jan 2019

        # From epoch onwards: 500.0
        assert months[12] == 500.0  # Jan 2020
        assert months[35] == 500.0  # Dec 2021

        assert len(months) == 36

    def test_step_function_length(self) -> None:
        """Output length matches month count."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _interpolate_temporal,
        )

        epoch_values = {2000: 100.0}
        months = _interpolate_temporal(
            epoch_values,
            start_year=2000,
            start_month=6,
            end_year=2001,
            end_month=5,
        )
        assert len(months) == 12


# ===================================================================
# GREEN — Full flow
# ===================================================================


class TestGhsPopViewpointFullFlowGreen:
    """End-to-end: synthetic GeoTIFFs → Parquet output."""

    def test_full_flow(self, tmp_path: Path) -> None:
        """Two epochs through the full pipeline produce valid Parquet."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        source_dir.mkdir()

        # Create two tiny GeoTIFFs (2x2 PRIO-GRID cells)
        _make_uniform_raster(
            source_dir / "GHS_POP_E2000_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=100.0,
            prio_rows=2,
            prio_cols=2,
        )
        _make_uniform_raster(
            source_dir / "GHS_POP_E2005_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=200.0,
            prio_rows=2,
            prio_cols=2,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "output.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2000, 2005),
            start_year=2000,
            start_month=1,
            end_year=2005,
            end_month=12,
        )

        result = build_ghspop_v1(cfg)

        assert result.output_path.exists()
        assert result.version == "ghspop_v1"
        assert result.output_digest != ""

        table = pq.read_table(result.output_path)
        assert "pgid" in table.column_names
        assert "month_id" in table.column_names
        assert "pop_count" in table.column_names

    def test_output_schema(self, tmp_path: Path) -> None:
        """Output has exactly the expected columns and types."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        _make_uniform_raster(
            source_dir / "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=50.0,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2020,),
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=12,
        )

        result = build_ghspop_v1(cfg)
        table = pq.read_table(result.output_path)

        import pyarrow as pa

        schema = table.schema
        assert schema.field("pgid").type == pa.int32()
        assert schema.field("month_id").type == pa.int32()
        assert schema.field("pop_count").type == pa.float64()

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        """Ledger entry written after successful build."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        _make_uniform_raster(
            source_dir / "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=1.0,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2020,),
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=1,
        )

        result = build_ghspop_v1(cfg)

        assert cfg.ledger_path.exists()
        entry = json.loads(
            cfg.ledger_path.read_text().strip().split("\n")[-1]
        )
        assert entry["dataset"] == "ghspop_viewpoint"
        assert entry["outcome"] == "success"
        assert entry["output_digest"] == result.output_digest
        assert "n_cells_output" in entry

    def test_registered_in_builders(self) -> None:
        """ghspop_v1 appears in builder registry."""
        import datafactory_viewpoint.builders.ghspop_v1  # noqa: F401
        from datafactory_viewpoint.builders import list_builders

        assert "ghspop_v1" in list_builders()

    def test_zero_population_cells_skipped(self, tmp_path: Path) -> None:
        """Cells with zero population are not written to output."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        # 2x2 PRIO-GRID cells: top-left has pop, rest are zero
        data = np.zeros((120, 120), dtype=np.float32)
        data[:60, :60] = 1.0
        _make_synthetic_geotiff(
            source_dir / "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif",
            data,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2020,),
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=1,
        )

        result = build_ghspop_v1(cfg)
        table = pq.read_table(result.output_path)

        pgids = table.column("pgid").to_pylist()
        # Only cells with nonzero population appear
        assert len(set(pgids)) == 1

    def test_pgid_mapping_correctness(self, tmp_path: Path) -> None:
        """Known raster position maps to correct PRIO-GRID cell ID.

        A 2x2 PRIO-GRID raster (120x120 pixels) has:
        - Raster row 0 = north = PRIO row 1 (from bottom)
        - Raster row 1 = south = PRIO row 0 (from bottom)
        - pgid = prio_row * ncol + col + 1

        For 2 cols:
          PRIO row 0, col 0 → pgid 1 (raster row 1, col 0)
          PRIO row 0, col 1 → pgid 2 (raster row 1, col 1)
          PRIO row 1, col 0 → pgid 3 (raster row 0, col 0)
          PRIO row 1, col 1 → pgid 4 (raster row 0, col 1)
        """
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        # Put distinct populations in each 60x60 block
        data = np.zeros((120, 120), dtype=np.float32)
        data[:60, :60] = 1.0     # raster top-left = north-west
        data[:60, 60:] = 2.0     # raster top-right = north-east
        data[60:, :60] = 3.0     # raster bottom-left = south-west
        data[60:, 60:] = 4.0     # raster bottom-right = south-east
        _make_synthetic_geotiff(
            source_dir / "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif",
            data,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2020,),
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=1,
        )

        build_ghspop_v1(cfg)
        table = pq.read_table(cfg.output_path)

        # Build pgid→pop_count mapping
        pgid_to_pop = dict(zip(
            table.column("pgid").to_pylist(),
            table.column("pop_count").to_pylist(),
            strict=True,
        ))

        # PRIO-GRID: row-major from bottom-left, 1-indexed
        # pgid 1 = south-west = raster bottom-left = 3.0 * 3600
        # pgid 2 = south-east = raster bottom-right = 4.0 * 3600
        # pgid 3 = north-west = raster top-left = 1.0 * 3600
        # pgid 4 = north-east = raster top-right = 2.0 * 3600
        assert pgid_to_pop[1] == 3.0 * 3600
        assert pgid_to_pop[2] == 4.0 * 3600
        assert pgid_to_pop[3] == 1.0 * 3600
        assert pgid_to_pop[4] == 2.0 * 3600

    def test_month_id_correctness(self, tmp_path: Path) -> None:
        """Month IDs follow VIEWS convention: 1 = January 1980."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        _make_uniform_raster(
            source_dir / "GHS_POP_E2000_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=1.0,
            prio_rows=1,
            prio_cols=1,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2000,),
            start_year=2000,
            start_month=1,
            end_year=2000,
            end_month=3,
        )

        build_ghspop_v1(cfg)
        table = pq.read_table(cfg.output_path)
        month_ids = sorted(table.column("month_id").to_pylist())

        # Jan 2000 = (2000-1980)*12 + 1 = 241
        # Feb 2000 = 242, Mar 2000 = 243
        assert month_ids == [241, 242, 243]

    def test_no_duplicate_pgid_month_id(self, tmp_path: Path) -> None:
        """Output has no duplicate (pgid, month_id) pairs."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        _make_uniform_raster(
            source_dir / "GHS_POP_E2000_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=10.0,
        )
        _make_uniform_raster(
            source_dir / "GHS_POP_E2005_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=20.0,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2000, 2005),
            start_year=2000,
            start_month=1,
            end_year=2005,
            end_month=12,
        )

        build_ghspop_v1(cfg)
        table = pq.read_table(cfg.output_path)

        pairs = list(zip(
            table.column("pgid").to_pylist(),
            table.column("month_id").to_pylist(),
            strict=True,
        ))
        assert len(pairs) == len(set(pairs))

    def test_source_dir_shortcut(self, tmp_path: Path) -> None:
        """build_ghspop_v1(source_dir=...) convenience API works."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        for epoch in (
            1975, 1980, 1985, 1990, 1995,
            2000, 2005, 2010, 2015, 2020, 2025, 2030,
        ):
            _make_uniform_raster(
                source_dir / f"GHS_POP_E{epoch}_GLOBE_R2023A_4326_30ss_V1_0.tif",
                value=1.0,
                prio_rows=1,
                prio_cols=1,
            )

        result = build_ghspop_v1(source_dir=source_dir)
        assert result.output_path.exists()
        assert result.n_events_output > 0


# ===================================================================
# BEIGE — Boundary conditions
# ===================================================================


class TestGhsPopViewpointBeige:
    """Boundary and edge cases."""

    def test_nodata_cells_treated_as_zero(self, tmp_path: Path) -> None:
        """Nodata (-200) pixels contribute zero to aggregation."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _aggregate_to_prio_grid,
        )

        data = np.full((60, 60), NODATA, dtype=np.float32)
        result = _aggregate_to_prio_grid(data, nodata=NODATA)
        assert result[0, 0] == 0.0

    def test_nodata_mixed_with_valid(self, tmp_path: Path) -> None:
        """Nodata pixels contribute zero; valid pixels sum normally."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _aggregate_to_prio_grid,
        )

        data = np.ones((60, 60), dtype=np.float32) * 10.0
        data[0, 0] = NODATA  # one nodata pixel
        result = _aggregate_to_prio_grid(data, nodata=NODATA)

        expected = (60 * 60 - 1) * 10.0
        np.testing.assert_allclose(result[0, 0], expected)

    def test_empty_epochs_raises(self) -> None:
        """Empty epochs tuple raises ValueError."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
        )

        with pytest.raises(ValueError, match="epoch"):
            GhsPopViewpointConfig(
                source_dir=Path("x"),
                epochs=(),
            )

    def test_unknown_epoch_raises(self) -> None:
        """Unknown epoch in viewpoint config raises ValueError."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
        )

        with pytest.raises(ValueError, match="1999"):
            GhsPopViewpointConfig(
                source_dir=Path("x"),
                epochs=(1999,),
            )

    def test_all_zero_raster_produces_empty_output(
        self, tmp_path: Path,
    ) -> None:
        """All-zero raster → empty Parquet output."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        _make_uniform_raster(
            source_dir / "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=0.0,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2020,),
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=12,
        )

        result = build_ghspop_v1(cfg)
        assert result.n_events_output == 0
        assert result.output_path.exists()


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestGhsPopViewpointRed:
    """Failure modes — fail loud (ADR-011)."""

    def test_missing_source_dir_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError when source_dir doesn't exist."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        cfg = GhsPopViewpointConfig(
            source_dir=tmp_path / "nonexistent",
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2020,),
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=12,
        )

        with pytest.raises(FileNotFoundError):
            build_ghspop_v1(cfg)

    def test_missing_epoch_file_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError when a configured epoch's TIF is missing."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
            build_ghspop_v1,
        )

        source_dir = tmp_path / "raw"
        source_dir.mkdir()
        # No TIF files created

        cfg = GhsPopViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(2020,),
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=12,
        )

        with pytest.raises(FileNotFoundError, match="2020"):
            build_ghspop_v1(cfg)

    def test_negative_population_clamped(self) -> None:
        """Negative pixel values are clamped to zero before aggregation."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _aggregate_to_prio_grid,
        )

        data = np.full((60, 60), -5.0, dtype=np.float32)
        result = _aggregate_to_prio_grid(data)
        assert result[0, 0] == 0.0

    def test_non_divisible_dimensions_raises(self) -> None:
        """Raster with dimensions not divisible by 60 raises ValueError."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            _aggregate_to_prio_grid,
        )

        data = np.ones((61, 120), dtype=np.float32)
        with pytest.raises(ValueError, match="divisible"):
            _aggregate_to_prio_grid(data)

    def test_no_args_raises(self) -> None:
        """build_ghspop_v1() with no arguments raises ValueError."""
        from datafactory_viewpoint.builders.ghspop_v1 import (
            build_ghspop_v1,
        )

        with pytest.raises(ValueError, match="Either"):
            build_ghspop_v1()
