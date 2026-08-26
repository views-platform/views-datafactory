#!/usr/bin/env python3
"""Does square-degree ranking pick a different GAUL polygon than true area?

`generate_area_majority_gaul.py` builds each PRIO-GRID cell as a 0.5-degree
box in raw EPSG:4326 and ranks candidate polygons by
`cell.intersection(poly).area`. That is **square degrees, not area**. At
60 degrees N one degree of longitude spans about half the ground distance
of one degree of latitude, so the measure overstates east-west extent by
roughly 2x.

The mitigation argument is that within one 0.5-degree cell every candidate
sits in the same narrow latitude band, so cos(lat) scales them all
near-equally and the *ranking* survives. That argument is plausible, is why
nobody caught this when ADR-039 was written, and has never been measured.
It weakens exactly where candidate polygons are asymmetric in latitude
inside the cell.

This script measures it. Pre-registered as H6 in
`reports/investigation_area_majority_gaul/pre_analysis_plan.md`.

No reprojection and no new dependency: the correction is a latitude-only
scale factor, so ranking by `sliver_area_deg * cos(sliver_centroid_lat)` is
equivalent to ranking by true area. H6's issue text (#387) proposed pyproj;
pyproj is not a dependency and its wheels bundle PROJ, the GDAL-family
chain ADR-039 rejected in Alternatives C and D.

Reads only. Writes one JSON of results. Never touches the delivered
parquets or the provenance ledger.

Usage:
    uv run python scripts/verify_area_majority_projection.py
    uv run python scripts/verify_area_majority_projection.py --min-abs-lat 45
    uv run python scripts/verify_area_majority_projection.py --self-test
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path

from shapely.geometry import box as shapely_box
from shapely.strtree import STRtree
from shapely.validation import make_valid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_area_majority_gaul import (  # noqa: E402
    _load_centroids,
    _load_gaul_polygons,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

DEFAULT_GAUL_L2 = Path(
    "data/raw/gaul_admin/shapefiles/GAUL_2024_L2/GAUL_2024_L2.shp"
)
DEFAULT_CENTROIDS = Path("data/raw/priogrid/shapefile/priogrid_centroid.shp")
DEFAULT_LAND_GAUL = Path("src/datafactory_query/land_gaul_pgids.json")
DEFAULT_OUT = Path(
    "reports/investigation_area_majority_gaul/projection_sensitivity.json"
)


def _rank_square_degrees(cell, polys, indices: list[int]) -> int:
    """The ranking the production script performs today.

    Deliberately duplicated from `_compute_cell_polygon_map` rather than
    imported: this script's whole job is to compare against what
    production does, and importing it would mean a change there silently
    changes the baseline this measurement is taken against.
    """
    best_idx, best = -1, 0.0
    for idx in indices:
        area = cell.intersection(polys[idx]).area
        if area > best:
            best_idx, best = idx, area
        elif area == best and area > 0 and idx < best_idx:
            best_idx = idx
    return best_idx


def _rank_cos_weighted(cell, polys, indices: list[int]) -> int:
    """The same ranking with each sliver scaled by cos(its own latitude).

    True area of a small region near latitude phi is proportional to
    `area_in_square_degrees * cos(phi)`. The constant of proportionality is
    identical for every candidate in one cell, so it cancels and only the
    per-sliver cos factor matters. Using each sliver's *own* centroid
    latitude is the point: a candidate occupying the northern strip of the
    cell gets a smaller factor than one occupying the southern strip, and
    that asymmetry is the only way the ranking can move.
    """
    best_idx, best = -1, 0.0
    for idx in indices:
        sliver = cell.intersection(polys[idx])
        if sliver.is_empty:
            continue
        weighted = sliver.area * math.cos(math.radians(sliver.centroid.y))
        if weighted > best:
            best_idx, best = idx, weighted
        elif weighted == best and weighted > 0 and idx < best_idx:
            best_idx = idx
    return best_idx


def _self_test() -> int:
    """Prove the measurement can detect a flip. A precondition for its result.

    Without this, "zero flips" is indistinguishable from a script that
    computes both rankings identically. The existing suite cannot stand in:
    `tests/test_area_majority.py` recomputes area-majority in square degrees
    inside its own oracles, so it is blind to this class by construction.

    Two candidates in a cell centred on 75 N, both spanning its full width,
    sized so the two rankings disagree:

      NORTH  74.25 + 0.798 .. 75.25, height 0.202 -> 0.10100 square degrees
      SOUTH  74.75 .. 74.95,         height 0.200 -> 0.10000 square degrees

    North has 1% more square degrees and wins that ranking. South sits about
    0.3 degrees lower, where cos(lat) is 2.1% larger, so it has more true
    area and wins the weighted ranking. A margin that small is the point:
    flips require near-ties, and near-ties are what the cancellation
    argument assumes away.
    """
    lat = 75.0
    cell = shapely_box(-0.25, lat - 0.25, 0.25, lat + 0.25)
    north = shapely_box(-0.25, 75.25 - 0.202, 0.25, 75.25)
    south = shapely_box(-0.25, 74.75, 0.25, 74.75 + 0.200)
    polys = [north, south]

    a_n = cell.intersection(north).area
    a_s = cell.intersection(south).area
    w_n = a_n * math.cos(math.radians(cell.intersection(north).centroid.y))
    w_s = a_s * math.cos(math.radians(cell.intersection(south).centroid.y))

    sq = _rank_square_degrees(cell, polys, [0, 1])
    cw = _rank_cos_weighted(cell, polys, [0, 1])

    log.info("self-test: square-degrees north=%.6f south=%.6f -> %s",
             a_n, a_s, "north" if sq == 0 else "south")
    log.info("self-test: cos-weighted  north=%.6f south=%.6f -> %s",
             w_n, w_s, "north" if cw == 0 else "south")

    if sq == cw:
        log.error(
            "SELF-TEST FAILED: both rankings agree on the synthetic cell, so "
            "this script cannot detect a flip. Any 'zero flips' result from "
            "it is meaningless. Fix the script before trusting Step 5."
        )
        return 1
    log.info("SELF-TEST PASSED: the two rankings disagree by construction, "
             "so a real flip would be detected.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gaul-l2", type=Path, default=DEFAULT_GAUL_L2)
    ap.add_argument("--centroids", type=Path, default=DEFAULT_CENTROIDS)
    ap.add_argument(
        "--land-gaul", type=Path, default=DEFAULT_LAND_GAUL,
        help="The cell list actually delivered to FAO. Counts are reported "
             "both over the whole grid and restricted to this set, because "
             "only the delivered subset has a consumer.",
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--min-abs-lat", type=float, default=55.0,
        help="Only cells with |lat| above this. Default 55 per H6.",
    )
    ap.add_argument(
        "--self-test", action="store_true",
        help="Run only the flip-detection drill and exit.",
    )
    args = ap.parse_args()

    if args.self_test:
        return _self_test()

    if _self_test() != 0:
        return 1

    log.info("Loading GAUL L2 polygons...")
    gaul_polys, gaul_records = _load_gaul_polygons(
        args.gaul_l2, ["gaul0_code", "gaul1_code", "gaul2_code"]
    )
    polys = [make_valid(p) for p in gaul_polys]
    tree = STRtree(polys)
    log.info("  %d polygons", len(polys))

    delivered = set(json.loads(args.land_gaul.read_text()))
    log.info("Loaded %d delivered land_gaul cells", len(delivered))

    log.info("Loading PRIO-GRID centroids...")
    cells = _load_centroids(args.centroids)
    high = [c for c in cells if abs(c[2]) > args.min_abs_lat]
    north = sum(1 for c in high if c[2] > 0)
    log.info("  %d cells total, %d with |lat| > %g (%d north, %d south)",
             len(cells), len(high), args.min_abs_lat, north, len(high) - north)

    border = 0
    border_delivered = 0
    flips: list[dict] = []
    for gid, lon, lat in high:
        cell = shapely_box(lon - 0.25, lat - 0.25, lon + 0.25, lat + 0.25)
        idx = [int(i) for i in tree.query(cell, predicate="intersects")]
        if len(idx) < 2:
            continue
        border += 1
        if gid in delivered:
            border_delivered += 1
        sq = _rank_square_degrees(cell, polys, idx)
        cw = _rank_cos_weighted(cell, polys, idx)
        if sq != cw:
            flips.append({
                "gid": gid, "lon": lon, "lat": lat,
                "candidates": len(idx),
                "delivered_to_fao": gid in delivered,
                "square_degree_winner": gaul_records[sq] if sq >= 0 else None,
                "cos_weighted_winner": gaul_records[cw] if cw >= 0 else None,
                "levels_affected": sorted(
                    k for k in gaul_records[sq]
                    if sq >= 0 and cw >= 0
                    and gaul_records[sq][k] != gaul_records[cw][k]
                ) if sq >= 0 and cw >= 0 else ["unassigned"],
            })

    log.info("")
    log.info("=== H6 RESULT ===")
    log.info("cells examined (|lat| > %g): %d", args.min_abs_lat, len(high))
    log.info("border cells (>1 candidate): %d (%d of them delivered)",
             border, border_delivered)
    log.info("FLIPS: %d (%d of them delivered)",
             len(flips), sum(1 for f in flips if f["delivered_to_fao"]))
    if not flips:
        log.info("H6 HOLDS. Square-degree ranking picks the same polygon as "
                 "true area for every border cell above %g degrees. The "
                 "cancellation argument is now measured, not assumed.",
                 args.min_abs_lat)
    else:
        log.info("H6 FALSIFIED. %d cells rank differently. Per the "
                 "pre-registered decision table: report the count and gid "
                 "list, and STOP. Do not correct the artifact and do not "
                 "contact FAO from this repository.", len(flips))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "hypothesis": "H6",
        "min_abs_lat": args.min_abs_lat,
        "cells_examined": len(high),
        "cells_north": north,
        "cells_delivered_above_lat": sum(1 for c in high if c[0] in delivered),
        "border_cells": border,
        "border_cells_delivered": border_delivered,
        "flip_count": len(flips),
        "flip_count_delivered": sum(1 for f in flips if f["delivered_to_fao"]),
        "flips": flips,
        "method": (
            "sliver.area * cos(radians(sliver.centroid.y)) versus "
            "sliver.area; no reprojection, no new dependency"
        ),
    }, indent=2) + "\n")
    log.info("Wrote %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
