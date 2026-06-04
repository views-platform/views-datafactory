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
