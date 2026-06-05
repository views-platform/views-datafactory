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

from pathlib import Path

import pyarrow.parquet as pq
import pytest
from shapely.geometry import Point, Polygon, box

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


# ---------------------------------------------------------------------------
# Phase 2 tests (#119): Hypothesis validation against real data
# ---------------------------------------------------------------------------

_CENTROID_DIR = Path("data/raw/gaul_admin")
_AREA_MAJ_DIR = Path("data/raw/gaul_admin_area_majority")


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
        centroid = _load_gid_value(_CENTROID_DIR / "gaul0_code.parquet")
        area_maj = _load_gid_value(_AREA_MAJ_DIR / "gaul0_code.parquet")
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
        centroid = _load_gid_value(_CENTROID_DIR / "gaul0_code.parquet")
        area_maj = _load_gid_value(_AREA_MAJ_DIR / "gaul0_code.parquet")
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
        centroid = _load_gid_value(_CENTROID_DIR / "gaul0_code.parquet")
        area_maj = _load_gid_value(_AREA_MAJ_DIR / "gaul0_code.parquet")
        lost = [
            gid for gid, val in centroid.items()
            if val > 0 and area_maj.get(gid, -1) <= 0
        ]
        assert len(lost) == 0, (
            f"H2 falsified: {len(lost)} cells lost valid assignment. "
            f"First 10: {lost[:10]}"
        )

    def test_valid_cell_count_increases(self) -> None:
        centroid = _load_gid_value(_CENTROID_DIR / "gaul0_code.parquet")
        area_maj = _load_gid_value(_AREA_MAJ_DIR / "gaul0_code.parquet")
        centroid_valid = sum(1 for v in centroid.values() if v > 0)
        area_maj_valid = sum(1 for v in area_maj.values() if v > 0)
        assert area_maj_valid >= centroid_valid, (
            f"H2 falsified: area-majority has fewer valid cells "
            f"({area_maj_valid}) than centroid ({centroid_valid})"
        )


@pytest.mark.falsification
class TestH3BorderRedistribution:
    """H3: 100-2,000 border cells change assignment."""

    def test_redistribution_count_in_expected_range(self) -> None:
        centroid = _load_gid_value(_CENTROID_DIR / "gaul0_code.parquet")
        area_maj = _load_gid_value(_AREA_MAJ_DIR / "gaul0_code.parquet")
        changed = [
            gid for gid in centroid
            if gid in area_maj and centroid[gid] != area_maj[gid]
        ]
        assert 100 <= len(changed) <= 2000, (
            f"H3 falsified: {len(changed)} cells changed assignment "
            f"(expected 100-2,000)"
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
