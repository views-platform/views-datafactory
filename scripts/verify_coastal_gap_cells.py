#!/usr/bin/env python3
"""Verify coastal_resolution_gap cells by polygon intersection.

For each of the 66 cells classified as coastal_resolution_gap in the
excluded-cell classification, this script checks whether:

  1. Any GAUL L2 polygon intersects the cell's 0.5-degree bounding box
  2. The expected admin unit (nearest_country / nearest_admin1) exists
     in the GAUL L2 shapefile at all

This replaces the distance-based proxy (proven unreliable by the
Fuvahmulah finding, ADR-043) with a direct polygon-presence check.

Results are written back into excluded_cell_classification.json with
`unit_verified` and `verification_note` fields on every
coastal_resolution_gap entry.

Usage:
    uv run python scripts/verify_coastal_gap_cells.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import shapefile as shp
from shapely.geometry import box as shapely_box
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.validation import make_valid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

SHP_PATH = Path("data/raw/gaul_admin/shapefiles/GAUL_2024_L2/GAUL_2024_L2.shp")
CLASSIFICATION_PATH = Path(
    "reports/investigation_gaul_excluded_cells/excluded_cell_classification.json"
)

FIELD_NAMES = [
    "gaul0_code", "gaul0_name",
    "gaul1_code", "gaul1_name",
    "gaul2_code", "gaul2_name",
    "iso3_code",
]


def _load_shapefile() -> tuple[list, list[dict]]:
    """Load GAUL L2 shapefile polygons and records."""
    polygons = []
    records = []
    n_null = 0

    with shp.Reader(str(SHP_PATH)) as sf:
        dbf_fields = [f[0] for f in sf.fields[1:]]
        field_indices = {fn: dbf_fields.index(fn) for fn in FIELD_NAMES}
        logger.info("Total records in shapefile: %d", len(sf))

        for sr in sf.iterShapeRecords():
            rec = {fn: sr.record[idx] for fn, idx in field_indices.items()}
            geo = sr.shape.__geo_interface__
            if geo["type"] == "Null":
                n_null += 1
                continue
            poly = shape(geo)
            if not poly.is_valid:
                poly = make_valid(poly)
            polygons.append(poly)
            records.append(rec)

    logger.info(
        "Loaded %d polygons, skipped %d null geometries",
        len(polygons), n_null,
    )
    return polygons, records


def _check_cell_intersection(
    lat: float,
    lon: float,
    tree: STRtree,
    polygons: list,
    records: list[dict],
) -> tuple[bool, list[dict]]:
    """Check if any GAUL polygon intersects the cell's 0.5-deg box.

    Returns (has_intersection, matching_records).
    """
    cell_box = shapely_box(lon - 0.25, lat - 0.25, lon + 0.25, lat + 0.25)
    indices = tree.query(cell_box, predicate="intersects")
    if len(indices) == 0:
        return False, []
    matches = [records[int(i)] for i in indices]
    return True, matches


def _check_unit_exists(
    country_name: str,
    admin1_name: str,
    records: list[dict],
) -> dict:
    """Search GAUL records for the expected admin unit.

    Returns dict with country_present, admin1_present, and match count.
    """
    country_matches = [
        r for r in records if r["gaul0_name"] == country_name
    ]
    admin1_matches = [
        r for r in country_matches if r["gaul1_name"] == admin1_name
    ]
    return {
        "country_present": len(country_matches) > 0,
        "country_polygon_count": len(country_matches),
        "admin1_present": len(admin1_matches) > 0,
        "admin1_polygon_count": len(admin1_matches),
    }


def _verify_entry(
    entry: dict,
    tree: STRtree,
    polygons: list,
    records: list[dict],
) -> dict:
    """Verify a single coastal_resolution_gap entry."""
    lat = entry["lat"]
    lon = entry["lon"]
    gid = entry["gid"]

    has_intersection, matches = _check_cell_intersection(
        lat, lon, tree, polygons, records,
    )

    country = entry.get("nearest_country", "")
    admin1 = entry.get("nearest_admin1", "")
    unit_info = _check_unit_exists(country, admin1, records)

    if has_intersection:
        country_names = sorted({m["gaul0_name"] for m in matches})
        note = (
            f"GAUL polygon(s) intersect cell box: {country_names}. "
            f"Cell was excluded from land_gaul despite overlap — "
            f"area-majority assignment returned -1 (overlap below threshold "
            f"or centroid in water)."
        )
        entry["unit_verified"] = True
        entry["verification_note"] = note
        entry["gaul_intersects_cell"] = True
    elif unit_info["country_present"] and unit_info["admin1_present"]:
        note = (
            f"No GAUL polygon intersects cell box. Expected unit "
            f"{country}/{admin1} exists in GAUL "
            f"({unit_info['admin1_polygon_count']} L2 polygons under "
            f"this admin1) but does not reach this 0.5-deg cell. "
            f"Genuine coastal resolution gap."
        )
        entry["unit_verified"] = True
        entry["verification_note"] = note
        entry["gaul_intersects_cell"] = False
    elif unit_info["country_present"] and not unit_info["admin1_present"]:
        note = (
            f"No GAUL polygon intersects cell box. Country {country} "
            f"has {unit_info['country_polygon_count']} polygons in GAUL "
            f"but admin1 '{admin1}' is absent. Possible source defect "
            f"(Fuvahmulah pattern) — the expected admin unit may be "
            f"missing from GAUL entirely."
        )
        entry["unit_verified"] = False
        entry["verification_note"] = note
        entry["gaul_intersects_cell"] = False
    else:
        note = (
            f"No GAUL polygon intersects cell box. Country '{country}' "
            f"not found in GAUL records at all. Likely legitimately "
            f"uncovered territory."
        )
        entry["unit_verified"] = True
        entry["verification_note"] = note
        entry["gaul_intersects_cell"] = False

    logger.info(
        "gid=%d (%.2f, %.2f): intersects=%s, unit_exists=%s/%s → verified=%s",
        gid, lat, lon,
        has_intersection,
        unit_info["country_present"],
        unit_info["admin1_present"],
        entry["unit_verified"],
    )
    return entry


def main() -> None:
    if not SHP_PATH.exists():
        logger.error("GAUL L2 shapefile not found: %s", SHP_PATH)
        raise SystemExit(1)

    classification = json.loads(CLASSIFICATION_PATH.read_text())
    coastal = [
        e for e in classification
        if e["classification"] == "coastal_resolution_gap"
    ]
    logger.info(
        "Found %d coastal_resolution_gap entries to verify", len(coastal),
    )

    already_verified = sum(
        1 for e in coastal if e.get("unit_verified") is not None
    )
    logger.info("Already verified: %d", already_verified)

    logger.info("Loading GAUL L2 shapefile...")
    polygons, records = _load_shapefile()

    logger.info("Building STRtree over %d polygons...", len(polygons))
    tree = STRtree(polygons)

    verified_count = 0
    defect_count = 0

    for entry in classification:
        if entry["classification"] != "coastal_resolution_gap":
            continue
        _verify_entry(entry, tree, polygons, records)
        verified_count += 1
        if not entry.get("unit_verified"):
            defect_count += 1

    logger.info(
        "Verified %d cells. Genuine gaps: %d. Possible defects: %d.",
        verified_count, verified_count - defect_count, defect_count,
    )

    if defect_count > 0:
        defects = [
            e for e in classification
            if e["classification"] == "coastal_resolution_gap"
            and not e.get("unit_verified")
        ]
        logger.warning("Possible source defects found:")
        for d in defects:
            logger.warning(
                "  gid=%d (%.2f, %.2f) — %s / %s",
                d["gid"], d["lat"], d["lon"],
                d.get("nearest_country"), d.get("nearest_admin1"),
            )

    CLASSIFICATION_PATH.write_text(
        json.dumps(classification, indent=2) + "\n"
    )
    logger.info("Updated %s", CLASSIFICATION_PATH)


if __name__ == "__main__":
    main()
