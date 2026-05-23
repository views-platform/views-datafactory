"""Tests for datafactory_priogrid -- PRIO-GRID spatial backbone.

Ported from views-metric-lab/tests/test_grid.py with adaptations:
- GridConfig no longer has path/URL fields (SRP redesign)
- Provenance tests use datafactory_provenance utilities
- harvester.py signature takes explicit paths instead of GridConfig
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from datafactory_priogrid.cell_generator import (
    generate_bounding_boxes,
    generate_grid,
    latlon_to_pgid,
    pgid_to_latlon,
)
from datafactory_priogrid.grid_config import GridConfig
from datafactory_priogrid.parity_validation import ParityResult, validate_parity

# ---------------------------------------------------------------------------
# GridConfig
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    cfg = GridConfig()
    assert cfg.resolution == 0.5
    assert cfg.nrow == 360
    assert cfg.ncol == 720
    assert cfg.n_cells == 259_200
    assert cfg.crs == "EPSG:4326"


def test_config_has_no_path_fields() -> None:
    """GridConfig should be pure spatial -- no data_dir, provenance_dir, or URL."""
    cfg = GridConfig()
    assert not hasattr(cfg, "data_dir")
    assert not hasattr(cfg, "provenance_dir")
    assert not hasattr(cfg, "shapefile_url")


def test_config_custom_resolution() -> None:
    cfg = GridConfig(resolution=0.25)
    assert cfg.nrow == 720
    assert cfg.ncol == 1440
    assert cfg.n_cells == 720 * 1440


def test_config_rejects_zero_resolution() -> None:
    with pytest.raises(ValueError, match="[Rr]esolution"):
        GridConfig(resolution=0.0)


def test_config_rejects_negative_resolution() -> None:
    with pytest.raises(ValueError, match="[Rr]esolution"):
        GridConfig(resolution=-1.0)


def test_config_rejects_inverted_bbox() -> None:
    with pytest.raises(ValueError, match="[Ww]est.*[Ee]ast|[Bb]ound"):
        GridConfig(west=10.0, east=-10.0)


def test_config_rejects_inverted_lat_bbox() -> None:
    with pytest.raises(ValueError, match="[Ss]outh.*[Nn]orth|[Bb]ound"):
        GridConfig(south=10.0, north=-10.0)


def test_config_rejects_indivisible_resolution() -> None:
    with pytest.raises(ValueError, match="[Dd]ivide|[Rr]esolution"):
        GridConfig(resolution=7.0)


# ---------------------------------------------------------------------------
# CIC-mandated frozen enforcement (Red)
# ---------------------------------------------------------------------------


class TestGridConfigRed:
    """CIC: GridConfig must be immutable (frozen dataclass)."""

    def test_mutation_rejected(self) -> None:
        cfg = GridConfig()
        with pytest.raises(AttributeError):
            cfg.resolution = 1.0  # type: ignore[misc]


class TestAssertGridShape:

    def test_valid_shape_passes(self) -> None:
        cfg = GridConfig()
        grid = np.zeros((1, cfg.nrow, cfg.ncol, 2))
        cfg.assert_grid_shape(grid)

    def test_wrong_height_raises(self) -> None:
        cfg = GridConfig()
        grid = np.zeros((1, 180, cfg.ncol, 2))
        with pytest.raises(AssertionError, match="spatial dims"):
            cfg.assert_grid_shape(grid)

    def test_wrong_width_raises(self) -> None:
        cfg = GridConfig()
        grid = np.zeros((1, cfg.nrow, 360, 2))
        with pytest.raises(AssertionError, match="spatial dims"):
            cfg.assert_grid_shape(grid)

    def test_non_array_raises_type_error(self) -> None:
        cfg = GridConfig()
        with pytest.raises(TypeError, match="Expected array"):
            cfg.assert_grid_shape("not an array")


class TestTemporalConfigRed:
    """CIC: TemporalConfig must be immutable (frozen dataclass)."""

    def test_mutation_rejected(self) -> None:
        from datafactory_priogrid.temporal_config import TemporalConfig

        cfg = TemporalConfig()
        with pytest.raises(AttributeError):
            cfg.start_year = 2000  # type: ignore[misc]


class TestSpatioTemporalGridRed:
    """CIC: SpatioTemporalGrid must be immutable (frozen dataclass)."""

    def test_mutation_rejected(self) -> None:
        from datafactory_priogrid.spatiotemporal import SpatioTemporalGrid

        grid = SpatioTemporalGrid()
        with pytest.raises(AttributeError):
            grid.grid_config = GridConfig(resolution=1.0)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Cell ID scheme -- canonical cells from PRIO-GRID R source
# ---------------------------------------------------------------------------


def test_cell_1_is_bottom_left() -> None:
    """Cell 1 should be at the south pole, date line."""
    pgids, lats, lons = generate_grid()
    idx = np.where(pgids == 1)[0][0]
    assert lats[idx] == pytest.approx(-89.75)
    assert lons[idx] == pytest.approx(-179.75)


def test_cell_720_is_bottom_right() -> None:
    """Cell 720 should be at the end of the first (southernmost) row."""
    pgids, lats, lons = generate_grid()
    idx = np.where(pgids == 720)[0][0]
    assert lats[idx] == pytest.approx(-89.75)
    assert lons[idx] == pytest.approx(179.75)


def test_cell_721_is_second_row() -> None:
    """Cell 721 should be start of second row from bottom."""
    pgids, lats, lons = generate_grid()
    idx = np.where(pgids == 721)[0][0]
    assert lats[idx] == pytest.approx(-89.25)
    assert lons[idx] == pytest.approx(-179.75)


def test_cell_259200_is_top_right() -> None:
    """Cell 259200 should be at the north pole, east edge."""
    pgids, lats, lons = generate_grid()
    idx = np.where(pgids == 259_200)[0][0]
    assert lats[idx] == pytest.approx(89.75)
    assert lons[idx] == pytest.approx(179.75)


def test_all_ids_unique() -> None:
    pgids, _, _ = generate_grid()
    assert len(np.unique(pgids)) == 259_200


def test_ids_contiguous() -> None:
    pgids, _, _ = generate_grid()
    assert pgids.min() == 1
    assert pgids.max() == 259_200


def test_id_formula() -> None:
    """Verify the formula: pgid = row_from_south * 720 + col_from_west + 1."""
    pgids, lats, lons = generate_grid()
    cfg = GridConfig()

    rows_from_south = (lats - cfg.south - cfg.resolution / 2) / cfg.resolution
    cols_from_west = (lons - cfg.west - cfg.resolution / 2) / cfg.resolution
    expected = (rows_from_south * cfg.ncol + cols_from_west + 1).astype(np.int32)

    np.testing.assert_array_equal(pgids, expected)


# ---------------------------------------------------------------------------
# Centroid bounds
# ---------------------------------------------------------------------------


def test_lat_bounds() -> None:
    _, lats, _ = generate_grid()
    assert lats.min() == pytest.approx(-89.75)
    assert lats.max() == pytest.approx(89.75)


def test_lon_bounds() -> None:
    _, _, lons = generate_grid()
    assert lons.min() == pytest.approx(-179.75)
    assert lons.max() == pytest.approx(179.75)


# ---------------------------------------------------------------------------
# Bounding boxes
# ---------------------------------------------------------------------------


def test_bounding_boxes_shape() -> None:
    pgids, w, s, e, n = generate_bounding_boxes()
    assert len(pgids) == 259_200
    assert len(w) == len(s) == len(e) == len(n) == 259_200


def test_bounding_boxes_cell_size() -> None:
    """Each cell should be 0.5 x 0.5 degrees."""
    _, w, s, e, n = generate_bounding_boxes()
    np.testing.assert_allclose(e - w, 0.5)
    np.testing.assert_allclose(n - s, 0.5)


def test_bounding_boxes_centroid_consistency() -> None:
    """Bounding box midpoints should match centroids."""
    _, w, s, e, n = generate_bounding_boxes()
    _, lats, lons = generate_grid()
    np.testing.assert_allclose((s + n) / 2, lats)
    np.testing.assert_allclose((w + e) / 2, lons)


# ---------------------------------------------------------------------------
# Coordinate <-> ID conversion
# ---------------------------------------------------------------------------


def test_pgid_to_latlon_cell_1() -> None:
    lat, lon = pgid_to_latlon(1)
    assert float(lat) == pytest.approx(-89.75)
    assert float(lon) == pytest.approx(-179.75)


def test_pgid_to_latlon_cell_259200() -> None:
    lat, lon = pgid_to_latlon(259_200)
    assert float(lat) == pytest.approx(89.75)
    assert float(lon) == pytest.approx(179.75)


def test_pgid_to_latlon_vectorised() -> None:
    lats, lons = pgid_to_latlon(np.array([1, 720, 721, 259_200]))
    np.testing.assert_allclose(lats, [-89.75, -89.75, -89.25, 89.75])
    np.testing.assert_allclose(lons, [-179.75, 179.75, -179.75, 179.75])


def test_latlon_to_pgid_centroid() -> None:
    """Centroid coordinates should round-trip to the same cell ID."""
    pgid = latlon_to_pgid(-89.75, -179.75)
    assert int(pgid) == 1


def test_latlon_to_pgid_vectorised() -> None:
    pgids = latlon_to_pgid(
        np.array([-89.75, 89.75]),
        np.array([-179.75, 179.75]),
    )
    np.testing.assert_array_equal(pgids, [1, 259_200])


def test_latlon_to_pgid_rejects_lat_above_90() -> None:
    with pytest.raises(ValueError, match="Latitude out of range"):
        latlon_to_pgid(91.0, 0.0)


def test_latlon_to_pgid_rejects_lat_below_neg90() -> None:
    with pytest.raises(ValueError, match="Latitude out of range"):
        latlon_to_pgid(-91.0, 0.0)


def test_latlon_to_pgid_rejects_lon_above_180() -> None:
    with pytest.raises(ValueError, match="Longitude out of range"):
        latlon_to_pgid(0.0, 181.0)


def test_latlon_to_pgid_rejects_lon_below_neg180() -> None:
    with pytest.raises(ValueError, match="Longitude out of range"):
        latlon_to_pgid(0.0, -181.0)


def test_latlon_to_pgid_boundary_valid() -> None:
    pgid = latlon_to_pgid(89.75, 179.75)
    assert int(pgid) == 259_200


def test_roundtrip_pgid_latlon() -> None:
    """All 259,200 cells should round-trip through pgid->latlon->pgid."""
    original, _, _ = generate_grid()
    lats, lons = pgid_to_latlon(original)
    recovered = latlon_to_pgid(lats, lons)
    np.testing.assert_array_equal(original, recovered)


def test_pgid_to_latlon_rejects_zero() -> None:
    with pytest.raises(ValueError, match="pgid"):
        pgid_to_latlon(0)


def test_pgid_to_latlon_rejects_above_range() -> None:
    with pytest.raises(ValueError, match="pgid"):
        pgid_to_latlon(259_201)


def test_pgid_to_latlon_rejects_negative() -> None:
    with pytest.raises(ValueError, match="pgid"):
        pgid_to_latlon(-1)


def test_pgid_to_latlon_rejects_mixed_array() -> None:
    with pytest.raises(ValueError, match="pgid"):
        pgid_to_latlon(np.array([1, 0, 259_200]))


# ---------------------------------------------------------------------------
# Custom resolution
# ---------------------------------------------------------------------------


def test_quarter_degree_grid() -> None:
    """0.25 degree grid should have 4x as many cells."""
    cfg = GridConfig(resolution=0.25)
    pgids, lats, lons = generate_grid(cfg)
    assert len(pgids) == 720 * 1440
    assert lats.min() == pytest.approx(-89.875)
    assert lons.min() == pytest.approx(-179.875)


# ---------------------------------------------------------------------------
# Temporal generators
# ---------------------------------------------------------------------------


def test_generate_time_steps_default_length() -> None:
    from datafactory_priogrid.temporal_generator import generate_time_steps

    steps = generate_time_steps()
    assert len(steps) == 456


def test_generate_time_steps_dtype() -> None:
    from datafactory_priogrid.temporal_generator import generate_time_steps

    steps = generate_time_steps()
    assert steps.dtype == np.dtype("datetime64[M]")


def test_generate_time_steps_custom_range() -> None:
    from datafactory_priogrid.temporal_config import TemporalConfig
    from datafactory_priogrid.temporal_generator import generate_time_steps

    cfg = TemporalConfig(start_year=2020, end_year=2020)
    steps = generate_time_steps(cfg)
    assert len(steps) == 12


def test_views_month_id_epoch() -> None:
    """January 1980 = month_id 1 (VIEWS convention)."""
    from datafactory_priogrid.temporal_generator import to_views_month_id

    result = to_views_month_id(np.datetime64("1980-01", "M"))
    assert int(result) == 1


def test_views_month_id_1989() -> None:
    """January 1989 = month_id 109."""
    from datafactory_priogrid.temporal_generator import to_views_month_id

    result = to_views_month_id(np.datetime64("1989-01", "M"))
    assert int(result) == 109


def test_from_views_month_id_epoch() -> None:
    from datafactory_priogrid.temporal_generator import from_views_month_id

    result = from_views_month_id(1)
    assert result == np.datetime64("1980-01", "M")


def test_views_month_id_roundtrip() -> None:
    from datafactory_priogrid.temporal_generator import (
        from_views_month_id,
        to_views_month_id,
    )

    dt = np.datetime64("2024-06", "M")
    recovered = from_views_month_id(to_views_month_id(dt))
    assert recovered == dt


# ---------------------------------------------------------------------------
# SpatioTemporalGrid
# ---------------------------------------------------------------------------


def test_spatiotemporal_default_shape() -> None:
    from datafactory_priogrid.spatiotemporal import SpatioTemporalGrid

    grid = SpatioTemporalGrid()
    assert grid.shape == (259_200, 456)


def test_spatiotemporal_delegates_n_cells() -> None:
    from datafactory_priogrid.spatiotemporal import SpatioTemporalGrid

    grid = SpatioTemporalGrid()
    assert grid.n_cells == grid.grid_config.n_cells


def test_spatiotemporal_delegates_n_steps() -> None:
    from datafactory_priogrid.spatiotemporal import SpatioTemporalGrid

    grid = SpatioTemporalGrid()
    assert grid.n_steps == grid.temporal_config.n_steps


def test_spatiotemporal_pgids_length() -> None:
    from datafactory_priogrid.spatiotemporal import SpatioTemporalGrid

    grid = SpatioTemporalGrid()
    assert len(grid.pgids) == grid.n_cells


def test_spatiotemporal_time_steps_length() -> None:
    from datafactory_priogrid.spatiotemporal import SpatioTemporalGrid

    grid = SpatioTemporalGrid()
    assert len(grid.time_steps) == grid.n_steps


def test_spatiotemporal_custom_config() -> None:
    from datafactory_priogrid.spatiotemporal import SpatioTemporalGrid

    grid = SpatioTemporalGrid(grid_config=GridConfig(resolution=90.0))
    assert grid.shape == (8, 456)


# ---------------------------------------------------------------------------
# Harvester (unit tests, no network) -- uses core provenance
# ---------------------------------------------------------------------------


def test_harvester_uses_core_provenance_functions() -> None:
    """Harvester must use datafactory_provenance, not reimplementations."""
    import datafactory_priogrid.shapefile_harvester as h
    import datafactory_provenance

    assert h.compute_content_digest is datafactory_provenance.compute_content_digest
    assert h.append_ledger_entry is datafactory_provenance.append_ledger_entry
    assert h.last_digest is datafactory_provenance.last_digest


def _make_fake_zip() -> bytes:
    """Create a minimal in-memory ZIP with a fake .shp file."""
    import io as _io
    import zipfile as _zf

    buf = _io.BytesIO()
    with _zf.ZipFile(buf, "w") as zf:
        zf.writestr("test.shp", "fake shapefile content")
        zf.writestr("test.dbf", "fake dbf content")
    return buf.getvalue()


def test_fetch_shapefile_full_flow(tmp_path: Path) -> None:
    """Mock download: extracts ZIP, writes provenance entry."""
    from unittest.mock import MagicMock, patch

    from datafactory_priogrid.shapefile_harvester import (
        ShapefileHarvesterConfig,
        fetch_shapefile,
    )

    fake_zip = _make_fake_zip()
    mock_resp = MagicMock()
    mock_resp.content = fake_zip
    mock_resp.raise_for_status = MagicMock()

    ledger = tmp_path / "provenance" / "ledger.jsonl"
    cfg = ShapefileHarvesterConfig(
        url="http://example.com/test.zip",
        data_dir=tmp_path / "data",
        ledger_path=ledger,
    )

    _target = "datafactory_http.retry.requests.request"
    with patch(_target, return_value=mock_resp):
        result = fetch_shapefile(cfg)

    assert result.exists()
    assert any(result.glob("*.shp"))
    assert ledger.exists()
    entry = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert entry["dataset"] == "priogrid_shapefile"
    assert entry["changed"] is True
    assert "content_digest" in entry


def test_fetch_shapefile_unchanged_content(tmp_path: Path) -> None:
    """When digest matches previous, record heartbeat without extraction."""
    from unittest.mock import MagicMock, patch

    from datafactory_priogrid.shapefile_harvester import (
        ShapefileHarvesterConfig,
        fetch_shapefile,
    )
    from datafactory_provenance import append_ledger_entry, compute_content_digest

    fake_zip = _make_fake_zip()
    digest = compute_content_digest(fake_zip)

    # Pre-populate ledger with matching digest
    ledger = tmp_path / "provenance" / "ledger.jsonl"
    append_ledger_entry(ledger, {"content_digest": digest})

    mock_resp = MagicMock()
    mock_resp.content = fake_zip
    mock_resp.raise_for_status = MagicMock()

    cfg = ShapefileHarvesterConfig(
        url="http://example.com/test.zip",
        data_dir=tmp_path / "data",
        ledger_path=ledger,
    )
    _target = "datafactory_http.retry.requests.request"
    with patch(_target, return_value=mock_resp):
        fetch_shapefile(cfg)

    lines = ledger.read_text().strip().splitlines()
    assert len(lines) == 2  # original + heartbeat
    heartbeat = json.loads(lines[1])
    assert heartbeat["changed"] is False


def test_fetch_shapefile_existing_files(tmp_path: Path) -> None:
    """When .shp files already exist, return without downloading."""
    from unittest.mock import patch

    from datafactory_priogrid.shapefile_harvester import (
        ShapefileHarvesterConfig,
        fetch_shapefile,
    )

    # Create existing shapefile
    shp_dir = tmp_path / "data" / "shapefile"
    shp_dir.mkdir(parents=True)
    (shp_dir / "existing.shp").write_text("fake")

    cfg = ShapefileHarvesterConfig(
        data_dir=tmp_path / "data",
        ledger_path=tmp_path / "ledger.jsonl",
    )
    with patch("datafactory_http.retry.requests.request") as mock_get:
        result = fetch_shapefile(cfg)

    mock_get.assert_not_called()
    assert result == shp_dir


def test_extract_zip_rejects_corrupt_content() -> None:
    """_extract_zip should raise BadZipFile on non-ZIP bytes."""
    import zipfile as _zf

    from datafactory_priogrid.shapefile_harvester import _extract_zip

    with pytest.raises(_zf.BadZipFile):
        _extract_zip(b"this is not a zip file", Path("/tmp/should_not_exist"))


# ---------------------------------------------------------------------------
# ADR-008 compliance: log before raise
# ---------------------------------------------------------------------------


class TestGridADR008Compliance:
    """ADR-008: structural failures must be both logged and raised."""

    _grid_logger = "datafactory_priogrid.grid_config"
    _temporal_logger = "datafactory_priogrid.temporal_config"

    def test_gridconfig_invalid_resolution_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        with (
            caplog.at_level(logging.ERROR, logger=self._grid_logger),
            pytest.raises(ValueError),
        ):
            GridConfig(resolution=-1.0)
        assert len([r for r in caplog.records if r.levelno >= logging.ERROR]) >= 1

    def test_temporalconfig_invalid_year_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from datafactory_priogrid.temporal_config import TemporalConfig

        with (
            caplog.at_level(logging.ERROR, logger=self._temporal_logger),
            pytest.raises(ValueError),
        ):
            TemporalConfig(start_year=-1)
        assert len([r for r in caplog.records if r.levelno >= logging.ERROR]) >= 1

    def test_pgid_out_of_range_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        with (
            caplog.at_level(
                logging.ERROR,
                logger="datafactory_priogrid.cell_generator",
            ),
            pytest.raises(ValueError),
        ):
            pgid_to_latlon(0)
        assert len([r for r in caplog.records if r.levelno >= logging.ERROR]) >= 1


# ---------------------------------------------------------------------------
# VIEWS month_id pre-epoch behavior (documented, not guarded)
# ---------------------------------------------------------------------------


def test_views_month_id_pre_epoch_returns_zero() -> None:
    """December 1979 is month_id 0 — documented behavior."""
    from datafactory_priogrid.temporal_generator import to_views_month_id

    assert int(to_views_month_id(np.datetime64("1979-12", "M"))) == 0


def test_views_month_id_pre_epoch_returns_negative() -> None:
    """January 1970 is month_id -119 — documented behavior."""
    from datafactory_priogrid.temporal_generator import to_views_month_id

    assert int(to_views_month_id(np.datetime64("1970-01", "M"))) == -119


# ---------------------------------------------------------------------------
# Parity validation (unit tests, mock reader)
# ---------------------------------------------------------------------------


def test_parity_result_structure() -> None:
    result = ParityResult(
        valid=True,
        n_cells_ours=259_200,
        n_cells_reference=259_200,
        n_matched=259_200,
    )
    assert result.valid
    assert result.n_matched == 259_200


class _MockReader:
    """Mock ReferenceGeometryReader that returns known centroids."""

    def __init__(self, cells: list[tuple[int, float, float]]) -> None:
        self._cells = cells

    def read(self, path: Path) -> list[tuple[int, float, float]]:
        return self._cells


def test_parity_perfect_match() -> None:
    """Validation should pass when reference matches our grid exactly."""
    cfg = GridConfig(resolution=90.0)
    pgids, lats, lons = generate_grid(cfg)
    ref_cells = [
        (int(p), float(la), float(lo))
        for p, la, lo in zip(pgids, lats, lons, strict=True)
    ]

    reader = _MockReader(ref_cells)
    result = validate_parity(reader, Path("/fake"), cfg)

    assert result.valid
    assert result.n_matched == len(pgids)
    assert result.max_centroid_error_deg == 0.0
    assert len(result.errors) == 0


def test_parity_detects_offset() -> None:
    """Validation should fail when reference centroids are shifted."""
    cfg = GridConfig(resolution=90.0)
    pgids, lats, lons = generate_grid(cfg)
    ref_cells = [
        (int(p), float(la) + 1.0, float(lo))
        for p, la, lo in zip(pgids, lats, lons, strict=True)
    ]

    reader = _MockReader(ref_cells)
    result = validate_parity(reader, Path("/fake"), cfg)

    assert not result.valid
    assert result.max_centroid_error_deg >= 1.0


def test_parity_detects_missing_cell() -> None:
    """Validation should flag cells present in reference but not in our grid."""
    cfg = GridConfig(resolution=90.0)
    ref_cells = [(999_999, 0.0, 0.0)]

    reader = _MockReader(ref_cells)
    result = validate_parity(reader, Path("/fake"), cfg)

    assert not result.valid
    assert any("999999" in e for e in result.errors)


# ---------------------------------------------------------------------------
# PyShpReader (unit tests with synthetic shapefiles, no network)
# ---------------------------------------------------------------------------


def _write_synthetic_shapefile(
    directory: Path,
    cells: list[tuple[int, float, float]],
    *,
    field_names: tuple[str, str, str] = ("gid", "ycoord", "xcoord"),
) -> Path:
    """Write a minimal shapefile with polygon geometry and attribute fields."""
    import shapefile as shp

    shp_path = directory / "test_grid"
    with shp.Writer(str(shp_path)) as w:
        w.field(field_names[0], "N", decimal=0)
        w.field(field_names[1], "N", decimal=4)
        w.field(field_names[2], "N", decimal=4)

        half = 0.25  # 0.5 degree cell
        for gid, lat, lon in cells:
            w.poly([
                [
                    (lon - half, lat - half),
                    (lon + half, lat - half),
                    (lon + half, lat + half),
                    (lon - half, lat + half),
                    (lon - half, lat - half),
                ]
            ])
            w.record(gid, lat, lon)

    return directory


def test_pyshp_reader_roundtrip(tmp_path: Path) -> None:
    """PyShpReader should recover the same (gid, lat, lon) we wrote."""
    from datafactory_priogrid.shapefile_reader import PyShpReader

    cells = [
        (1, -89.75, -179.75),
        (720, -89.75, 179.75),
        (129_961, 0.25, 0.25),
        (259_200, 89.75, 179.75),
    ]
    shp_dir = _write_synthetic_shapefile(tmp_path, cells)

    reader = PyShpReader()
    result = reader.read(shp_dir)

    assert len(result) == 4
    for (exp_gid, exp_lat, exp_lon), (got_gid, got_lat, got_lon) in zip(
        cells, result, strict=True
    ):
        assert got_gid == exp_gid
        assert got_lat == pytest.approx(exp_lat)
        assert got_lon == pytest.approx(exp_lon)


def test_pyshp_reader_alternative_field_names(tmp_path: Path) -> None:
    """Reader should discover fields regardless of naming convention."""
    from datafactory_priogrid.shapefile_reader import PyShpReader

    cells = [(42, 10.25, 30.75)]
    shp_dir = _write_synthetic_shapefile(
        tmp_path, cells, field_names=("pgid", "latitude", "longitude")
    )

    reader = PyShpReader()
    result = reader.read(shp_dir)

    assert len(result) == 1
    assert result[0][0] == 42
    assert result[0][1] == pytest.approx(10.25)
    assert result[0][2] == pytest.approx(30.75)


def test_pyshp_reader_geometry_fallback(tmp_path: Path) -> None:
    """When centroid fields are missing, reader should use bounding box."""
    import shapefile as shp

    from datafactory_priogrid.shapefile_reader import PyShpReader

    shp_path = tmp_path / "no_coords"
    with shp.Writer(str(shp_path)) as w:
        w.field("gid", "N", decimal=0)
        half = 0.25
        lat, lon = 5.25, 10.75
        w.poly([
            [
                (lon - half, lat - half),
                (lon + half, lat - half),
                (lon + half, lat + half),
                (lon - half, lat + half),
                (lon - half, lat - half),
            ]
        ])
        w.record(99)

    reader = PyShpReader()
    result = reader.read(tmp_path)

    assert len(result) == 1
    assert result[0][0] == 99
    assert result[0][1] == pytest.approx(5.25)
    assert result[0][2] == pytest.approx(10.75)


def test_pyshp_reader_parity_integration(tmp_path: Path) -> None:
    """Full integration: write synthetic shapefile, read it, validate parity."""
    from datafactory_priogrid.shapefile_reader import PyShpReader

    cfg = GridConfig(resolution=90.0)
    pgids, lats, lons = generate_grid(cfg)
    cells = [
        (int(p), float(la), float(lo))
        for p, la, lo in zip(pgids, lats, lons, strict=True)
    ]
    shp_dir = _write_synthetic_shapefile(tmp_path, cells)

    reader = PyShpReader()
    result = validate_parity(reader, shp_dir, cfg)

    assert result.valid
    assert result.n_matched == len(pgids)
    assert result.max_centroid_error_deg == 0.0


def test_parity_provenance_recording(tmp_path: Path) -> None:
    """record_parity_result should write valid JSONL via core provenance."""
    from datafactory_priogrid.parity_validation import record_parity_result

    ledger = tmp_path / "parity_validation.jsonl"
    result = ParityResult(
        valid=True,
        n_cells_ours=8,
        n_cells_reference=8,
        n_matched=8,
    )

    record_parity_result(result, ledger)
    assert ledger.exists()

    entry = json.loads(ledger.read_text().strip())
    assert entry["valid"] is True
    assert entry["n_matched"] == 8
    assert "timestamp" in entry  # auto-added by core


# ---------------------------------------------------------------------------
# ShapefileHarvesterConfig (G10)
# ---------------------------------------------------------------------------


class TestShapefileHarvesterConfigGreen:

    def test_defaults(self) -> None:
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
        )

        cfg = ShapefileHarvesterConfig()
        assert cfg.timeout == 120
        assert cfg.max_retries == 3


class TestShapefileHarvesterConfigBeige:

    def test_rejects_zero_timeout(self) -> None:
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
        )

        with pytest.raises(ValueError, match="timeout"):
            ShapefileHarvesterConfig(timeout=0)

    def test_rejects_zero_retries(self) -> None:
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
        )

        with pytest.raises(ValueError, match="max_retries"):
            ShapefileHarvesterConfig(max_retries=0)
