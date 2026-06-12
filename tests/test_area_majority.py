"""Test harness for area-majority GAUL assignment (#117).

Synthetic GAUL polygons and PRIO-GRID cells designed so that centroid
and area-majority methods give different results for specific cells.

Geometry layout::

      0.0    0.5   0.8  1.0          2.0
  2.0 ┌────────────────┬─────────────┐
      │       A        │      B      │
  1.0 ├────┬───────────┼─────────────┤
      │    │ C peninsul│             │
  0.6 │    ├───────────┤             │
  0.4 │ C  │     D     │      D      │
      │    │           │             │
  0.0 └────┴───────────┴─────────────┘
       Below y=0 is "water" (no GAUL polygon).

  Country C is an L-shape: main body [0, 0.5]×[0, 1] plus a narrow
  peninsula [0.5, 0.8]×[0.4, 0.6]. Country D fills the rest of the
  bottom row: [0.5, 2]×[0, 1] minus C's peninsula.

  This creates:
  - Inland cell (gid=1) at centroid (0.25, 1.5): fully inside A
  - Border cell (gid=5) at centroid (0.75, 0.5): centroid lands in
    C's peninsula, but cell box [0.5,1.0]×[0.25,0.75] has 76% in D
  - Coastal cell (gid=9) at centroid (1.25, -0.1): centroid in water,
    but cell box [1.0,1.5]×[-0.35,0.15] overlaps D above y=0
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely.geometry import MultiPolygon, Point, Polygon, box

# -- GAUL codes for the 4 synthetic countries --
GAUL_A = 100
GAUL_B = 200
GAUL_C = 300
GAUL_D = 400


def _build_synthetic_gaul() -> tuple[list[Polygon], list[dict]]:
    """Build 4 country polygons with C having a narrow peninsula.

    Returns (polygons, records) where each record has gaul0_code.
    Country C's peninsula [0.5, 0.8]×[0.4, 0.6] contains the border
    cell's centroid at (0.75, 0.5), but the peninsula is narrow so
    D has majority area in the cell box [0.5, 1.0]×[0.25, 0.75].
    """
    c_peninsula = box(0.5, 0.4, 0.8, 0.6)
    polygons = [
        box(0.0, 1.0, 1.0, 2.0),                    # A: top-left
        box(1.0, 1.0, 2.0, 2.0),                    # B: top-right
        box(0.0, 0.0, 0.5, 1.0).union(c_peninsula),  # C: L-shape
        box(0.5, 0.0, 2.0, 1.0).difference(c_peninsula),  # D: with notch
    ]
    records = [
        {"gaul0_code": GAUL_A},
        {"gaul0_code": GAUL_B},
        {"gaul0_code": GAUL_C},
        {"gaul0_code": GAUL_D},
    ]
    return polygons, records


def _build_synthetic_cells() -> list[tuple[int, float, float]]:
    """Build 9 PRIO-GRID cells as (gid, centroid_lon, centroid_lat).

    Cell polygons are centroid +/- 0.25 degrees (0.5 x 0.5 boxes).
    Three key cells:
      gid=1: inland, centroid (0.25, 1.5) — fully in A
      gid=5: border, centroid (0.75, 0.5) — centroid in C, majority in D
      gid=9: coastal, centroid (1.25, -0.1) — centroid in water
    """
    cells = []
    gid = 1
    for lat_center in [1.5, 0.5, -0.1]:
        for lon_center in [0.25, 0.75, 1.25]:
            cells.append((gid, lon_center, lat_center))
            gid += 1
    return cells


def _cell_box(lon: float, lat: float) -> Polygon:
    """Build a 0.5-degree cell box from a centroid."""
    return box(lon - 0.25, lat - 0.25, lon + 0.25, lat + 0.25)


GID_INLAND = 1   # centroid (0.25, 1.5)
GID_BORDER = 5   # centroid (0.75, 0.5)
GID_COASTAL = 9  # centroid (1.25, -0.1)


def _expected_centroid_assignments() -> dict[int, int]:
    """Expected gaul0_code under point-in-polygon (centroid method).

    Coastal cells get -1 (centroid in water). Border cell gets C
    (centroid at (0.75, 0.5) is inside C's peninsula).
    """
    polys, recs = _build_synthetic_gaul()
    cells = _build_synthetic_cells()
    assignments: dict[int, int] = {}
    for gid, lon, lat in cells:
        pt = Point(lon, lat)
        assigned = -1
        for poly, rec in zip(polys, recs, strict=True):
            if poly.contains(pt):
                assigned = rec["gaul0_code"]
                break
        assignments[gid] = assigned
    return assignments


def _expected_area_majority_assignments() -> dict[int, int]:
    """Expected gaul0_code under area-majority method.

    Coastal cells get assigned to the country with most overlap above y=0.
    Border cell gets D (76% of cell area in D, 24% in C's peninsula).
    """
    polys, recs = _build_synthetic_gaul()
    cells = _build_synthetic_cells()
    assignments: dict[int, int] = {}
    for gid, lon, lat in cells:
        cell_poly = _cell_box(lon, lat)
        best_code = -1
        best_area = 0.0
        for poly, rec in zip(polys, recs, strict=True):
            intersection = cell_poly.intersection(poly)
            area = intersection.area
            if area > best_area:
                best_area = area
                best_code = rec["gaul0_code"]
            elif area == best_area and area > 0:
                best_code = min(best_code, rec["gaul0_code"])
        assignments[gid] = best_code
    return assignments


class TestAreaMajorityFixtures:
    """Verify the synthetic fixtures are geometrically valid."""

    def test_gaul_polygons_are_valid(self) -> None:
        polys, _ = _build_synthetic_gaul()
        for i, poly in enumerate(polys):
            assert poly.is_valid, f"Polygon {i} is invalid"

    def test_gaul_polygons_do_not_overlap(self) -> None:
        polys, _ = _build_synthetic_gaul()
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                intersection = polys[i].intersection(polys[j])
                assert intersection.area == 0.0, (
                    f"Polygons {i} and {j} overlap with area {intersection.area}"
                )

    def test_cell_polygons_are_half_degree(self) -> None:
        cells = _build_synthetic_cells()
        for gid, lon, lat in cells:
            cell = _cell_box(lon, lat)
            bounds = cell.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            assert abs(width - 0.5) < 1e-10, f"gid={gid} width={width}"
            assert abs(height - 0.5) < 1e-10, f"gid={gid} height={height}"

    def test_coastal_cell_centroid_outside_all_polygons(self) -> None:
        polys, _ = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        _, lon, lat = cells[GID_COASTAL - 1]
        pt = Point(lon, lat)
        for i, poly in enumerate(polys):
            assert not poly.contains(pt), (
                f"Coastal cell centroid ({lon}, {lat}) is inside polygon {i}"
            )

    def test_coastal_cell_polygon_overlaps_gaul(self) -> None:
        polys, _ = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        _, lon, lat = cells[GID_COASTAL - 1]
        cell = _cell_box(lon, lat)
        overlaps_any = any(
            cell.intersects(p) and cell.intersection(p).area > 0
            for p in polys
        )
        assert overlaps_any, "Coastal cell box must overlap at least one GAUL polygon"

    def test_border_cell_centroid_in_c_but_majority_in_d(self) -> None:
        polys, recs = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        _, lon, lat = cells[GID_BORDER - 1]

        pt = Point(lon, lat)
        centroid_country = -1
        for poly, rec in zip(polys, recs, strict=True):
            if poly.contains(pt):
                centroid_country = rec["gaul0_code"]
                break
        assert centroid_country == GAUL_C, (
            f"Border cell centroid should be in C ({GAUL_C}), got {centroid_country}"
        )

        cell = _cell_box(lon, lat)
        areas: dict[int, float] = {}
        for poly, rec in zip(polys, recs, strict=True):
            area = cell.intersection(poly).area
            if area > 0:
                areas[rec["gaul0_code"]] = area
        majority_country = max(areas, key=areas.get)  # type: ignore[arg-type]
        assert majority_country == GAUL_D, (
            f"Border cell majority should be D ({GAUL_D}), got {majority_country}. "
            f"Areas: {areas}"
        )

    def test_centroid_and_area_majority_differ_for_key_cells(self) -> None:
        centroid = _expected_centroid_assignments()
        area_maj = _expected_area_majority_assignments()

        assert centroid[GID_COASTAL] == -1, "Centroid should miss coastal cell"
        assert area_maj[GID_COASTAL] == GAUL_D, (
            "Area-majority should assign coastal to D"
        )

        assert centroid[GID_BORDER] == GAUL_C, "Centroid should assign border to C"
        assert area_maj[GID_BORDER] == GAUL_D, "Area-majority should assign border to D"

        assert centroid[GID_INLAND] == area_maj[GID_INLAND] == GAUL_A, (
            "Both methods should agree on inland cell"
        )

    def test_nine_cells_in_fixture(self) -> None:
        cells = _build_synthetic_cells()
        assert len(cells) == 9

    def test_four_gaul_polygons_in_fixture(self) -> None:
        polys, recs = _build_synthetic_gaul()
        assert len(polys) == 4
        assert len(recs) == 4

    def test_all_gaul_codes_unique(self) -> None:
        _, recs = _build_synthetic_gaul()
        codes = [r["gaul0_code"] for r in recs]
        assert len(codes) == len(set(codes))


# ---------------------------------------------------------------------------
# Phase 1 tests (#118): area_majority_join() — TDD
# ---------------------------------------------------------------------------

def _import_area_majority_join():
    """Import area_majority_join from the generation script."""
    import importlib.util
    from pathlib import Path

    script = (
        Path(__file__).resolve().parent.parent
        / "scripts" / "generate_area_majority_gaul.py"
    )
    spec = importlib.util.spec_from_file_location(
        "generate_area_majority_gaul", script,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.area_majority_join


class TestGenerationScriptGreen:
    """Happy-path tests for area_majority_join()."""

    def test_coastal_cell_gets_valid_assignment(self) -> None:
        """Coastal cell (centroid in water) must be recovered by area-majority."""
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = join(cells, polys, recs)
        assert result[GID_COASTAL] == GAUL_D, (
            f"Coastal cell should be D ({GAUL_D}), "
            f"got {result[GID_COASTAL]}"
        )

    def test_inland_cell_preserved(self) -> None:
        """Inland cell must keep its centroid-era assignment."""
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = join(cells, polys, recs)
        assert result[GID_INLAND] == GAUL_A, (
            f"Inland cell should stay A ({GAUL_A}), got {result[GID_INLAND]}"
        )

    def test_border_cell_gets_majority_country(self) -> None:
        """Border cell must be assigned to D (76% area), not C (centroid)."""
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = join(cells, polys, recs)
        assert result[GID_BORDER] == GAUL_D, (
            f"Border cell should be D ({GAUL_D}), got {result[GID_BORDER]}"
        )

    def test_output_covers_all_cells(self) -> None:
        """Result must contain an entry for every input cell."""
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = join(cells, polys, recs)
        expected_gids = {gid for gid, _, _ in cells}
        assert set(result.keys()) == expected_gids

    def test_all_assignments_match_area_majority_oracle(self) -> None:
        """Every cell assignment must match the reference oracle."""
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = join(cells, polys, recs)
        oracle = _expected_area_majority_assignments()
        for gid in oracle:
            assert result[gid] == oracle[gid], (
                f"gid={gid}: join gave {result[gid]}, oracle says {oracle[gid]}"
            )

    def test_all_codes_are_known_gaul_or_minus_one(self) -> None:
        """No garbage codes — every value is a known GAUL code or -1."""
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = join(cells, polys, recs)
        valid_codes = {r["gaul0_code"] for r in recs} | {-1}
        for gid, code in result.items():
            assert code in valid_codes, (
                f"gid={gid} got unknown code {code}, valid: {valid_codes}"
            )


class TestGenerationScriptBeige:
    """Edge-case tests for area_majority_join()."""

    def test_no_overlap_returns_minus_one(self) -> None:
        """A cell entirely outside all polygons gets -1."""
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul()
        water_cell = [(999, 5.0, -5.0)]  # far from any polygon
        result = join(water_cell, polys, recs)
        assert result[999] == -1

    def test_single_overlap_assigns_directly(self) -> None:
        """A cell overlapping exactly one polygon gets that code."""
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul()
        # Cell deep inside A — only one polygon overlaps
        inland_only = [(1, 0.25, 1.5)]
        result = join(inland_only, polys, recs)
        assert result[1] == GAUL_A

    def test_tied_areas_use_lowest_gaul_code(self) -> None:
        """When two polygons have equal intersection area, lowest code wins."""
        join = _import_area_majority_join()
        # Two equal-sized polygons splitting a cell exactly in half
        poly_left = box(0.0, 0.0, 0.5, 1.0)
        poly_right = box(0.5, 0.0, 1.0, 1.0)
        polys = [poly_left, poly_right]
        recs = [{"gaul0_code": 500}, {"gaul0_code": 200}]
        # Cell centered at (0.5, 0.5) — straddles the boundary equally
        cells = [(1, 0.5, 0.5)]
        result = join(cells, polys, recs)
        assert result[1] == 200, (
            f"Tied areas should pick lowest code (200), got {result[1]}"
        )


class TestGenerationScriptRed:
    """Failure-mode tests for area_majority_join()."""

    def test_invalid_geometry_handled(self) -> None:
        """Invalid polygons (bowtie) must be fixed, not crash."""
        join = _import_area_majority_join()
        # Bowtie polygon — self-intersecting, invalid
        bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
        assert not bowtie.is_valid
        polys = [bowtie]
        recs = [{"gaul0_code": 100}]
        cells = [(1, 0.5, 0.5)]
        result = join(cells, polys, recs)
        assert 1 in result  # must not crash

    def test_empty_input_returns_empty(self) -> None:
        """Zero cells in → empty dict out."""
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul()
        result = join([], polys, recs)
        assert result == {}

    def test_string_field_tiebreaker_no_crash(self) -> None:
        """C-248: string field with area tie must not raise TypeError."""
        join = _import_area_majority_join()
        left = box(0.0, 0.0, 0.5, 1.0)
        right = box(0.5, 0.0, 1.0, 1.0)
        polys = [left, right]
        recs = [{"gaul0_name": "Alpha"}, {"gaul0_name": "Bravo"}]
        cells = [(1, 0.5, 0.5)]  # equal split → tiebreaker fires
        result = join(
            cells, polys, recs, field_name="gaul0_name", default="",
        )
        assert result[1] == "Alpha", (
            f"Tiebreaker should pick lexicographic min 'Alpha', got {result[1]!r}"
        )


# ---------------------------------------------------------------------------
# Name file generation tests (#132)
# ---------------------------------------------------------------------------


class TestWriteParquetDtype:
    """OCP: _write_area_majority_parquet supports int32 and utf8."""

    def test_write_parquet_int_dtype_unchanged(self, tmp_path: Path) -> None:
        """Existing integer behavior preserved with default dtype."""
        sys.path.insert(0, str(Path("scripts")))
        from generate_area_majority_gaul import _write_area_majority_parquet

        ledger_path = tmp_path / "ledger.jsonl"
        ledger_path.touch()
        result = _write_area_majority_parquet(
            "test_code", {1: 10, 2: 20, 3: -1},
            tmp_path, ledger_path,
        )
        t = pq.read_table(tmp_path / "test_code.parquet")
        assert t.schema.field("value").type == pa.int32()
        assert result["n_valid"] == 2
        assert result["n_unassigned"] == 1

    def test_write_parquet_string_dtype(self, tmp_path: Path) -> None:
        """String values written with pa.utf8() dtype."""
        sys.path.insert(0, str(Path("scripts")))
        from generate_area_majority_gaul import _write_area_majority_parquet

        ledger_path = tmp_path / "ledger.jsonl"
        ledger_path.touch()
        result = _write_area_majority_parquet(
            "test_name", {1: "Ethiopia", 2: "Kenya", 3: ""},
            tmp_path, ledger_path, dtype=pa.utf8(),
        )
        t = pq.read_table(tmp_path / "test_name.parquet")
        assert t.schema.field("value").type == pa.utf8()
        assert result["n_valid"] == 2
        assert result["n_unassigned"] == 1

    def test_string_validity_counting(self, tmp_path: Path) -> None:
        """Non-empty = valid, empty = unassigned for string dtype."""
        sys.path.insert(0, str(Path("scripts")))
        from generate_area_majority_gaul import _write_area_majority_parquet

        ledger_path = tmp_path / "ledger.jsonl"
        ledger_path.touch()
        result = _write_area_majority_parquet(
            "test_count", {1: "A", 2: "", 3: "B", 4: "", 5: "C"},
            tmp_path, ledger_path, dtype=pa.utf8(),
        )
        assert result["n_valid"] == 3
        assert result["n_unassigned"] == 2


class TestVariableListSeparation:
    """CRP: code and name variable lists are disjoint."""

    def test_name_variables_separate_from_code(self) -> None:
        sys.path.insert(0, str(Path("scripts")))
        from generate_area_majority_gaul import (
            GAUL_CODE_VARIABLES,
            GAUL_NAME_VARIABLES,
        )

        code_names = {v[0] for v in GAUL_CODE_VARIABLES}
        name_names = {v[0] for v in GAUL_NAME_VARIABLES}
        assert code_names.isdisjoint(name_names), (
            f"Overlap: {code_names & name_names}"
        )


# ---------------------------------------------------------------------------
# Phase 2 tests (#119): Hypothesis validation against real data
# ---------------------------------------------------------------------------

_CENTROID_DIR = Path("data/raw/gaul_admin")
_AREA_MAJ_DIR = Path("data/raw/gaul_admin_area_majority")
_CENTROID_BACKUP = _CENTROID_DIR / "centroid_backup"


def _load_gid_value(parquet_path: Path) -> dict[int, int]:
    """Load a (gid, value) Parquet file into a dict."""
    t = pq.read_table(parquet_path)
    gids = t.column("gid").to_pylist()
    vals = t.column("value").to_pylist()
    return dict(zip(gids, vals, strict=True))


@pytest.mark.falsification
class TestH1CoastalCellRecovery:
    """H1: All coastal cells with centroid in water get valid codes."""

    def test_recovered_cells_have_valid_codes(self) -> None:
        centroid = _load_gid_value(
            _CENTROID_BACKUP / "gaul0_code.parquet",
        )
        area_maj = _load_gid_value(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        centroid_gids = set(centroid.keys())
        recovered = {
            gid: val for gid, val in area_maj.items()
            if gid not in centroid_gids and val != -1
        }
        for gid, val in recovered.items():
            assert val > 0, (
                f"Recovered gid={gid} has invalid code {val}"
            )

    def test_recovered_cell_count_exceeds_zero(self) -> None:
        centroid = _load_gid_value(
            _CENTROID_BACKUP / "gaul0_code.parquet",
        )
        area_maj = _load_gid_value(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        centroid_gids = set(centroid.keys())
        recovered = [
            gid for gid, val in area_maj.items()
            if gid not in centroid_gids and val > 0
        ]
        assert len(recovered) > 0, (
            "H1 falsified: no coastal cells were recovered"
        )


@pytest.mark.falsification
class TestH2NoAssignmentLoss:
    """H2: No cell with valid centroid assignment loses it."""

    def test_no_valid_cell_loses_assignment(self) -> None:
        centroid = _load_gid_value(
            _CENTROID_BACKUP / "gaul0_code.parquet",
        )
        area_maj = _load_gid_value(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        lost = [
            gid for gid, val in centroid.items()
            if val > 0 and area_maj.get(gid, -1) <= 0
        ]
        assert len(lost) == 0, (
            f"H2 falsified: {len(lost)} cells lost valid "
            f"assignment. First 10: {lost[:10]}"
        )

    def test_valid_cell_count_increases(self) -> None:
        centroid = _load_gid_value(
            _CENTROID_BACKUP / "gaul0_code.parquet",
        )
        area_maj = _load_gid_value(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        centroid_valid = sum(
            1 for v in centroid.values() if v > 0
        )
        area_maj_valid = sum(
            1 for v in area_maj.values() if v > 0
        )
        assert area_maj_valid >= centroid_valid, (
            f"H2 falsified: area-majority has fewer valid "
            f"cells ({area_maj_valid}) than centroid "
            f"({centroid_valid})"
        )


@pytest.mark.falsification
class TestH3BorderRedistribution:
    """H3: 100-2,000 border cells change assignment."""

    def test_redistribution_count_in_expected_range(self) -> None:
        centroid = _load_gid_value(
            _CENTROID_BACKUP / "gaul0_code.parquet",
        )
        area_maj = _load_gid_value(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        changed = [
            gid for gid in centroid
            if gid in area_maj
            and centroid[gid] != area_maj[gid]
        ]
        assert 100 <= len(changed) <= 2000, (
            f"H3 falsified: {len(changed)} cells changed "
            f"assignment (expected 100-2,000)"
        )


@pytest.mark.falsification
class TestH5FormatCompatibility:
    """H5: Output schema identical to centroid files."""

    def test_parquet_schema_matches_centroid(self) -> None:
        centroid_schema = pq.read_schema(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        area_maj_schema = pq.read_schema(
            _AREA_MAJ_DIR / "gaul0_code.parquet",
        )
        assert centroid_schema.equals(area_maj_schema), (
            f"Schema mismatch: centroid={centroid_schema}, "
            f"area_maj={area_maj_schema}"
        )

    def test_all_three_levels_exist(self) -> None:
        for level in ("gaul0_code", "gaul1_code", "gaul2_code"):
            path = _AREA_MAJ_DIR / f"{level}.parquet"
            assert path.exists(), (
                f"Missing area-majority file: {path}"
            )


# ---------------------------------------------------------------------------
# Phase 3 tests (#120): Pipeline integration
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PIPELINE_SCRIPT = _REPO_ROOT / "scripts" / "refresh_pipeline.sh"
_GAUL_LEDGER = (
    _REPO_ROOT / "provenance" / "gaul_admin" / "ingestion_ledger.jsonl"
)


@pytest.mark.falsification
class TestI1AssemblyCompatibility:
    """I1: Area-majority files in canonical dir after integration."""

    def test_canonical_dir_has_full_grid_row_count(self) -> None:
        for level in ("gaul0_code", "gaul1_code", "gaul2_code"):
            t = pq.read_table(_CENTROID_DIR / f"{level}.parquet")
            assert t.num_rows == 259200, (
                f"{level}: expected 259,200 rows, "
                f"got {t.num_rows}"
            )

    def test_canonical_gids_are_superset_of_backup(self) -> None:
        canonical = _load_gid_value(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        backup = _load_gid_value(
            _CENTROID_BACKUP / "gaul0_code.parquet",
        )
        missing = set(backup.keys()) - set(canonical.keys())
        assert len(missing) == 0, (
            f"{len(missing)} backup gids missing from "
            f"canonical. First 10: {sorted(missing)[:10]}"
        )


@pytest.mark.falsification
class TestI2PipelineWiring:
    """I2: refresh_pipeline.sh runs area-majority after harvest."""

    def test_refresh_pipeline_runs_area_majority_after_harvest(
        self,
    ) -> None:
        text = _PIPELINE_SCRIPT.read_text()
        harvest_pos = text.find("harvest_gaul.py")
        area_maj_pos = text.find("generate_area_majority_gaul.py")
        assert harvest_pos >= 0, (
            "harvest_gaul.py not found in refresh_pipeline.sh"
        )
        assert area_maj_pos >= 0, (
            "generate_area_majority_gaul.py not found in "
            "refresh_pipeline.sh"
        )
        assert area_maj_pos > harvest_pos, (
            "area-majority must run after harvest_gaul.py"
        )

    def test_area_majority_overwrites_to_gaul_admin_dir(
        self,
    ) -> None:
        text = _PIPELINE_SCRIPT.read_text()
        idx = text.find("generate_area_majority_gaul.py")
        assert idx >= 0
        after = text[idx:idx + 300]
        assert "data/raw/gaul_admin" in after, (
            "area-majority script must write to "
            "data/raw/gaul_admin"
        )


@pytest.mark.falsification
class TestI3ProvenanceIntegrity:
    """I3: Provenance ledger records area-majority method."""

    def test_area_majority_ledger_has_all_three_levels(
        self,
    ) -> None:
        import json

        assert _GAUL_LEDGER.exists(), (
            f"Ledger not found: {_GAUL_LEDGER}"
        )
        entries = [
            json.loads(line)
            for line in _GAUL_LEDGER.read_text().strip().splitlines()
        ]
        am_entries = [
            e for e in entries
            if e.get("method") == "area_majority"
        ]
        am_versions = {e["version"] for e in am_entries}
        expected = {"gaul0_code", "gaul1_code", "gaul2_code"}
        assert am_versions >= expected, (
            f"Missing area_majority ledger entries: "
            f"{expected - am_versions}"
        )


# ---------------------------------------------------------------------------
# Phase 4 tests (#121): Splash zone verification
# ---------------------------------------------------------------------------


@pytest.mark.falsification
class TestS1CMAggregation:
    """S1: CM aggregation works correctly with area-majority codes."""

    def test_cm_fewer_unassigned_cells_than_centroid(self) -> None:
        area_maj = _load_gid_value(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        backup = _load_gid_value(
            _CENTROID_BACKUP / "gaul0_code.parquet",
        )
        am_unassigned = sum(
            1 for v in area_maj.values() if v <= 0
        )
        # Centroid had 86,091 rows total, all matched (no -1 rows
        # stored). The full grid has 259,200 cells, so centroid left
        # 259,200 - 86,091 = 173,109 cells unmapped.
        centroid_unassigned = 259200 - len(backup)
        assert am_unassigned < centroid_unassigned, (
            f"Area-majority has {am_unassigned} unassigned cells, "
            f"expected fewer than centroid's {centroid_unassigned}"
        )

    def test_cm_all_valid_codes_are_positive(self) -> None:
        area_maj = _load_gid_value(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        valid = {
            gid: val for gid, val in area_maj.items()
            if val != -1
        }
        bad = [
            (gid, val) for gid, val in valid.items()
            if val <= 0
        ]
        assert len(bad) == 0, (
            f"{len(bad)} cells have non-(-1) but non-positive "
            f"codes. First 10: {bad[:10]}"
        )

    def test_cm_no_silent_loss_of_valid_cells(self) -> None:
        area_maj = _load_gid_value(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        backup = _load_gid_value(
            _CENTROID_BACKUP / "gaul0_code.parquet",
        )
        am_valid = sum(1 for v in area_maj.values() if v > 0)
        backup_valid = sum(1 for v in backup.values() if v > 0)
        assert am_valid >= backup_valid, (
            f"Area-majority has {am_valid} valid cells, "
            f"fewer than centroid's {backup_valid}"
        )


@pytest.mark.falsification
class TestS2ConsumerBridge:
    """S2: Consumer bridge maps gaul0_code correctly."""

    def test_consumer_feature_rename_includes_gaul0_code(
        self,
    ) -> None:
        script = (
            _REPO_ROOT / "scripts" / "generate_consumer_data.py"
        )
        text = script.read_text()
        assert '"gaul0_code": "c_id"' in text, (
            "FEATURE_RENAME must map gaul0_code → c_id"
        )


@pytest.mark.falsification
class TestS3RegionSubsetting:
    """S3: Region subsetting stable after area-majority swap."""

    def test_region_pgids_unchanged_from_name_file(self) -> None:
        from datafactory_query.regions import (
            _load_country_pgids,
            load_region_pgids,
        )

        country_pgids = _load_country_pgids(_CENTROID_DIR)
        assert len(country_pgids) > 0, (
            "No countries loaded from gaul0_name.parquet"
        )
        for region in ("africa", "middle_east", "africa_me"):
            pgids = load_region_pgids(region, gaul_dir=_CENTROID_DIR)
            assert len(pgids) > 0, (
                f"Region {region!r} returned empty pgid set"
            )

    def test_name_file_row_count_matches_code_file(self) -> None:
        name_table = pq.read_table(
            _CENTROID_DIR / "gaul0_name.parquet",
        )
        code_table = pq.read_table(
            _CENTROID_DIR / "gaul0_code.parquet",
        )
        assert name_table.num_rows == code_table.num_rows, (
            f"Name file ({name_table.num_rows} rows) should match "
            f"code file ({code_table.num_rows} rows) after "
            f"area-majority name generation (#132)"
        )


# ---------------------------------------------------------------------------
# C-246 tests (#136): _compute_cell_polygon_map() — TDD
# ---------------------------------------------------------------------------


def _import_compute_cell_polygon_map():
    """Import _compute_cell_polygon_map from the generation script."""
    import importlib.util

    script = (
        Path(__file__).resolve().parent.parent
        / "scripts" / "generate_area_majority_gaul.py"
    )
    spec = importlib.util.spec_from_file_location(
        "generate_area_majority_gaul", script,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._compute_cell_polygon_map


def _build_synthetic_gaul_multifield() -> tuple[list, list[dict]]:
    """Build 4 country polygons with multi-field records.

    Same geometry as _build_synthetic_gaul() but records include
    gaul0_code, gaul0_name, and gaul1_code to verify that
    _compute_cell_polygon_map returns polygon indices, not field values.
    """
    c_peninsula = box(0.5, 0.4, 0.8, 0.6)
    polygons = [
        box(0.0, 1.0, 1.0, 2.0),
        box(1.0, 1.0, 2.0, 2.0),
        box(0.0, 0.0, 0.5, 1.0).union(c_peninsula),
        box(0.5, 0.0, 2.0, 1.0).difference(c_peninsula),
    ]
    records = [
        {"gaul0_code": GAUL_A, "gaul0_name": "Alpha", "gaul1_code": 1001},
        {"gaul0_code": GAUL_B, "gaul0_name": "Bravo", "gaul1_code": 2001},
        {"gaul0_code": GAUL_C, "gaul0_name": "Charlie", "gaul1_code": 3001},
        {"gaul0_code": GAUL_D, "gaul0_name": "Delta", "gaul1_code": 4001},
    ]
    return polygons, records


class TestCellPolygonMapGreen:
    """Happy-path tests for _compute_cell_polygon_map() (C-246)."""

    def test_inland_cell_maps_to_polygon(self) -> None:
        """Inland cell (fully inside A) maps to polygon index 0."""
        cpm = _import_compute_cell_polygon_map()
        polys, _ = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = cpm(cells, polys)
        assert result[GID_INLAND] == 0, (
            f"Inland cell should map to poly index 0 (A), got {result[GID_INLAND]}"
        )

    def test_border_cell_maps_to_majority_polygon(self) -> None:
        """Border cell maps to polygon index 3 (D has 76% area)."""
        cpm = _import_compute_cell_polygon_map()
        polys, _ = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = cpm(cells, polys)
        assert result[GID_BORDER] == 3, (
            f"Border cell should map to poly index 3 (D), got {result[GID_BORDER]}"
        )

    def test_coastal_cell_maps_to_polygon(self) -> None:
        """Coastal cell (centroid in water) still maps to a valid polygon."""
        cpm = _import_compute_cell_polygon_map()
        polys, _ = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = cpm(cells, polys)
        assert result[GID_COASTAL] != -1, (
            "Coastal cell should map to a polygon via area overlap"
        )

    def test_output_covers_all_cells(self) -> None:
        """Result has an entry for every input GID."""
        cpm = _import_compute_cell_polygon_map()
        polys, _ = _build_synthetic_gaul()
        cells = _build_synthetic_cells()
        result = cpm(cells, polys)
        expected_gids = {gid for gid, _, _ in cells}
        assert set(result.keys()) == expected_gids

    def test_returns_polygon_indices_not_field_values(self) -> None:
        """All returned values are polygon indices (0-3), not GAUL codes."""
        cpm = _import_compute_cell_polygon_map()
        polys, _ = _build_synthetic_gaul_multifield()
        cells = _build_synthetic_cells()
        result = cpm(cells, polys)
        gaul_codes = {GAUL_A, GAUL_B, GAUL_C, GAUL_D}
        for gid, poly_idx in result.items():
            if poly_idx == -1:
                continue
            assert 0 <= poly_idx < len(polys), (
                f"gid={gid}: poly_idx={poly_idx} out of range [0, {len(polys)})"
            )
            assert poly_idx not in gaul_codes, (
                f"gid={gid}: returned GAUL code {poly_idx}, not a polygon index"
            )

    def test_no_overlap_returns_minus_one(self) -> None:
        """Cell far from any polygon gets -1."""
        cpm = _import_compute_cell_polygon_map()
        polys, _ = _build_synthetic_gaul()
        far_cell = [(999, 50.0, 50.0)]
        result = cpm(far_cell, polys)
        assert result[999] == -1


class TestCellPolygonMapBeige:
    """Edge-case tests for _compute_cell_polygon_map() (C-246)."""

    def test_empty_cells_returns_empty(self) -> None:
        cpm = _import_compute_cell_polygon_map()
        polys, _ = _build_synthetic_gaul()
        assert cpm([], polys) == {}

    def test_single_cell_single_polygon(self) -> None:
        """Trivial 1x1 case: one cell fully inside one polygon."""
        cpm = _import_compute_cell_polygon_map()
        poly = box(0, 0, 2, 2)
        cells = [(1, 1.0, 1.0)]
        result = cpm(cells, [poly])
        assert result[1] == 0

    def test_tie_broken_by_lowest_polygon_index(self) -> None:
        """Two polygons with equal area → lowest index wins."""
        cpm = _import_compute_cell_polygon_map()
        left = box(0.0, 0.0, 0.5, 1.0)
        right = box(0.5, 0.0, 1.0, 1.0)
        cells = [(1, 0.5, 0.5)]  # centroid on the boundary, equal split
        result = cpm(cells, [left, right])
        assert result[1] == 0, (
            f"Equal-area tie should go to polygon index 0, got {result[1]}"
        )

    def test_touching_but_zero_area_intersection(self) -> None:
        """Polygon that shares only an edge (zero area) is not assigned."""
        cpm = _import_compute_cell_polygon_map()
        poly = box(1.0, 0.0, 2.0, 1.0)
        cells = [(1, 0.5, 0.5)]  # cell is [0.25, 0.75] x [0.25, 0.75]
        result = cpm(cells, [poly])
        assert result[1] == -1, (
            "Zero-area intersection should not assign a polygon"
        )


class TestCellPolygonMapRed:
    """Failure-mode tests for _compute_cell_polygon_map() (C-246)."""

    def test_invalid_polygon_handled(self) -> None:
        """Self-intersecting (bowtie) polygon is fixed by make_valid."""
        cpm = _import_compute_cell_polygon_map()
        bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
        assert not bowtie.is_valid
        cells = [(1, 0.5, 0.5)]
        result = cpm(cells, [bowtie])
        assert 1 in result  # must not crash

    def test_multipolygon_input(self) -> None:
        """MultiPolygon geometry (common in GAUL L2) works correctly."""
        cpm = _import_compute_cell_polygon_map()
        mp = MultiPolygon([box(0, 0, 0.4, 1), box(0.6, 0, 1.0, 1)])
        cells = [(1, 0.2, 0.5), (2, 0.8, 0.5)]
        result = cpm(cells, [mp])
        assert result[1] == 0
        assert result[2] == 0


class TestCellPolygonMapEquivalence:
    """Cross-check _compute_cell_polygon_map against area_majority_join (C-246)."""

    def test_polygon_map_plus_records_equals_join(self) -> None:
        """records[cell_poly_map[gid]] == area_majority_join result for all cells."""
        cpm = _import_compute_cell_polygon_map()
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul_multifield()
        cells = _build_synthetic_cells()

        poly_map = cpm(cells, polys)
        join_result = join(cells, polys, recs, field_name="gaul0_code")

        for gid, _, _ in cells:
            poly_idx = poly_map[gid]
            expected = -1 if poly_idx == -1 else recs[poly_idx]["gaul0_code"]
            assert expected == join_result[gid], (
                f"gid={gid}: poly_map→records gives {expected}, "
                f"join gives {join_result[gid]}"
            )

    def test_tiebreaker_consistency(self) -> None:
        """For monotonically increasing codes, polygon-index and
        field-value tiebreakers agree."""
        cpm = _import_compute_cell_polygon_map()
        join = _import_area_majority_join()
        left = box(0.0, 0.0, 0.5, 1.0)
        right = box(0.5, 0.0, 1.0, 1.0)
        polys = [left, right]
        recs = [{"gaul0_code": 10}, {"gaul0_code": 20}]
        cells = [(1, 0.5, 0.5)]

        poly_idx = cpm(cells, polys)[1]
        join_val = join(cells, polys, recs)[1]
        assert recs[poly_idx]["gaul0_code"] == join_val, (
            f"Tiebreakers disagree: poly_map→{recs[poly_idx]['gaul0_code']}, "
            f"join→{join_val}"
        )

    def test_sentinel_consistency(self) -> None:
        """Both paths return sentinel for cells with no polygon overlap."""
        cpm = _import_compute_cell_polygon_map()
        join = _import_area_majority_join()
        polys, recs = _build_synthetic_gaul_multifield()
        far_cell = [(999, 50.0, 50.0)]

        assert cpm(far_cell, polys)[999] == -1
        assert join(far_cell, polys, recs)[999] == -1
