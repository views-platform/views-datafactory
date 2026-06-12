#!/usr/bin/env python3
"""Investigate the 82 land cells excluded from land_gaul.

Probes the raw GAUL L2 shapefile to determine whether missing
coverage is an FAO source defect or a datafactory extraction issue.

For each excluded cell:
  1. Checks whether the cell's archipelago/country has other polygons
  2. Finds the nearest GAUL polygon and its distance
  3. Classifies: "legitimately_uncovered" vs "suspected_data_defect"

Usage:
    uv run python scripts/investigate_gaul_excluded_cells.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import shapefile as shp
from shapely.geometry import box as shapely_box
from shapely.geometry import shape
from shapely.strtree import STRtree

from datafactory_priogrid import pgid_to_latlon

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

SHP_PATH = Path("data/raw/gaul_admin/shapefiles/GAUL_2024_L2/GAUL_2024_L2.shp")
LAND_JSON = Path("src/datafactory_query/land_pgids.json")
LAND_GAUL_JSON = Path("src/datafactory_query/land_gaul_pgids.json")
OUTPUT_DIR = Path("reports/investigation_gaul_excluded_cells")

TARGET_COUNTRIES = ["Portugal", "Maldives", "Kiribati"]


def _load_excluded_cells() -> list[int]:
    """Return the 82 land cells without GAUL coverage."""
    land = set(json.loads(LAND_JSON.read_text()))
    land_gaul = set(json.loads(LAND_GAUL_JSON.read_text()))
    return sorted(land - land_gaul)


def _scan_shapefile() -> (
    tuple[list, list[dict], int, list[dict]]
):
    """Read GAUL L2 shapefile, collecting polygons and null geometry info.

    Returns:
        (polygons, records, n_null, null_records)
        - polygons: list of shapely geometries (non-null only)
        - records: list of dicts with gaul0/1/2 name+code, iso3 (non-null only)
        - n_null: count of null geometries encountered
        - null_records: attribute records for null geometries
    """
    field_names = [
        "gaul0_code", "gaul0_name",
        "gaul1_code", "gaul1_name",
        "gaul2_code", "gaul2_name",
        "iso3_code",
    ]

    polygons = []
    records = []
    n_null = 0
    null_records = []

    with shp.Reader(str(SHP_PATH)) as sf:
        dbf_fields = [f[0] for f in sf.fields[1:]]
        field_indices = {
            fn: dbf_fields.index(fn) for fn in field_names
        }
        logger.info(
            "Shapefile fields: %s", dbf_fields,
        )
        logger.info("Total records in shapefile: %d", len(sf))

        for sr in sf.iterShapeRecords():
            rec = {
                fn: sr.record[idx]
                for fn, idx in field_indices.items()
            }
            geo = sr.shape.__geo_interface__
            if geo["type"] == "Null":
                n_null += 1
                null_records.append(rec)
                continue
            polygons.append(shape(geo))
            records.append(rec)

    logger.info(
        "Loaded %d polygons, skipped %d null geometries",
        len(polygons), n_null,
    )
    return polygons, records, n_null, null_records


def _probe_target_countries(
    records: list[dict],
    polygons: list,
) -> dict[str, list[dict]]:
    """Find all GAUL polygons belonging to target countries."""
    results: dict[str, list[dict]] = {c: [] for c in TARGET_COUNTRIES}

    for i, rec in enumerate(records):
        name = rec["gaul0_name"]
        if name in TARGET_COUNTRIES:
            bbox = polygons[i].bounds  # (minx, miny, maxx, maxy)
            results[name].append({
                "gaul0_name": rec["gaul0_name"],
                "gaul1_name": rec["gaul1_name"],
                "gaul2_name": rec["gaul2_name"],
                "gaul0_code": rec["gaul0_code"],
                "iso3_code": rec["iso3_code"],
                "bbox": list(bbox),
            })

    return results


def _find_nearest_polygon(
    lat: float,
    lon: float,
    tree: STRtree,
    polygons: list,
    records: list[dict],
) -> dict:
    """Find nearest GAUL polygon to a cell centroid.

    Expands search radius until a match is found.
    """
    for radius in [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 45.0]:
        search = shapely_box(
            lon - radius, lat - radius,
            lon + radius, lat + radius,
        )
        indices = tree.query(search, predicate="intersects")
        if len(indices) > 0:
            from shapely.geometry import Point
            centroid = Point(lon, lat)
            best_dist = float("inf")
            best_idx = -1
            for idx in indices:
                idx = int(idx)
                dist = centroid.distance(polygons[idx])
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            return {
                "nearest_country": records[best_idx]["gaul0_name"],
                "nearest_admin1": records[best_idx]["gaul1_name"],
                "nearest_admin2": records[best_idx]["gaul2_name"],
                "distance_deg": round(best_dist, 4),
                "search_radius": radius,
            }

    return {
        "nearest_country": "NONE_FOUND",
        "nearest_admin1": "",
        "nearest_admin2": "",
        "distance_deg": 999.0,
        "search_radius": 45.0,
    }


def _classify_cell(
    nearest: dict,
    country_polygons: dict[str, list[dict]],
) -> str:
    """Classify a cell as legitimately_uncovered or suspected_data_defect."""
    dist = nearest["distance_deg"]
    country = nearest["nearest_country"]

    if dist < 1.0 and country in TARGET_COUNTRIES:
        return "suspected_data_defect"
    if dist < 0.5:
        return "suspected_data_defect"
    if dist > 5.0:
        return "legitimately_uncovered"

    return "near_coverage_boundary"


def main() -> None:
    excluded = _load_excluded_cells()
    logger.info("Excluded cells: %d", len(excluded))

    lats, lons = pgid_to_latlon(np.array(excluded))

    logger.info("Loading GAUL L2 shapefile (this takes ~2 min)...")
    polygons, records, n_null, null_records = _scan_shapefile()

    # --- Phase 1: Null geometry audit ---
    print("\n" + "=" * 70)
    print("PHASE 1: Null Geometry Audit")
    print("=" * 70)
    print(f"Total null geometries in shapefile: {n_null}")
    if null_records:
        print("\nNull geometry records:")
        for nr in null_records:
            print(
                f"  {nr['gaul0_name']} / {nr['gaul1_name']}"
                f" / {nr['gaul2_name']}"
                f" (code={nr['gaul0_code']})"
            )
        target_nulls = [
            nr for nr in null_records
            if nr["gaul0_name"] in TARGET_COUNTRIES
        ]
        if target_nulls:
            print(f"\n  *** TARGET COUNTRY NULL GEOMETRIES: {len(target_nulls)} ***")
            for nr in target_nulls:
                print(
                    f"    {nr['gaul0_name']}"
                    f" / {nr['gaul1_name']}"
                    f" / {nr['gaul2_name']}"
                )
        else:
            print(
                "  No null geometries belong to"
                f" target countries {TARGET_COUNTRIES}"
            )
    else:
        print("  No null geometries found in shapefile.")

    # --- Phase 2: Target country polygon inventory ---
    print("\n" + "=" * 70)
    print("PHASE 2: Target Country Polygon Inventory")
    print("=" * 70)

    country_polys = _probe_target_countries(records, polygons)
    for country, polys in country_polys.items():
        print(f"\n{country}: {len(polys)} polygons")
        if polys:
            for p in sorted(polys, key=lambda x: x["gaul1_name"]):
                print(
                    f"  L1={p['gaul1_name']:<30s}"
                    f"  L2={p['gaul2_name']:<30s}"
                    f"  bbox=[{p['bbox'][0]:8.3f}, {p['bbox'][1]:8.3f},"
                    f" {p['bbox'][2]:8.3f}, {p['bbox'][3]:8.3f}]"
                )

    # --- Phase 3: Nearest polygon for each excluded cell ---
    print("\n" + "=" * 70)
    print("PHASE 3: Nearest GAUL Polygon per Excluded Cell")
    print("=" * 70)

    logger.info("Building spatial index...")
    tree = STRtree(polygons)

    classifications = []
    for i, gid in enumerate(excluded):
        lat = float(lats[i])
        lon = float(lons[i])
        nearest = _find_nearest_polygon(
            lat, lon, tree, polygons, records,
        )
        classification = _classify_cell(nearest, country_polys)

        entry = {
            "gid": gid,
            "lat": lat,
            "lon": lon,
            "classification": classification,
            **nearest,
        }
        classifications.append(entry)

        print(
            f"  gid={gid:<8d}  lat={lat:7.2f}  lon={lon:8.2f}"
            f"  dist={nearest['distance_deg']:6.3f}°"
            f"  near={nearest['nearest_country']:<25s}"
            f"  admin1={nearest['nearest_admin1']:<25s}"
            f"  → {classification}"
        )

    # --- Phase 4: Summary ---
    print("\n" + "=" * 70)
    print("PHASE 4: Classification Summary")
    print("=" * 70)

    from collections import Counter
    counts = Counter(c["classification"] for c in classifications)
    for cls, count in sorted(counts.items()):
        print(f"  {cls}: {count}")

    defects = [
        c for c in classifications
        if c["classification"] == "suspected_data_defect"
    ]
    if defects:
        print(f"\nSuspected data defects ({len(defects)}):")
        for d in defects:
            print(
                f"  gid={d['gid']}  lat={d['lat']:.2f}  lon={d['lon']:.2f}"
                f"  nearest={d['nearest_country']}/{d['nearest_admin1']}"
                f"  dist={d['distance_deg']:.3f}°"
            )

    boundary = [
        c for c in classifications
        if c["classification"] == "near_coverage_boundary"
    ]
    if boundary:
        print(f"\nNear coverage boundary ({len(boundary)}):")
        for b in boundary:
            print(
                f"  gid={b['gid']}  lat={b['lat']:.2f}  lon={b['lon']:.2f}"
                f"  nearest={b['nearest_country']}/{b['nearest_admin1']}"
                f"  dist={b['distance_deg']:.3f}°"
            )

    # --- Write output ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "excluded_cell_classification.json"
    out_path.write_text(json.dumps(classifications, indent=2))
    logger.info("Wrote %s", out_path)

    country_out = OUTPUT_DIR / "target_country_polygons.json"
    country_out.write_text(json.dumps(country_polys, indent=2))
    logger.info("Wrote %s", country_out)

    null_out = OUTPUT_DIR / "null_geometries.json"
    null_out.write_text(json.dumps({
        "n_null": n_null,
        "null_records": null_records,
    }, indent=2))
    logger.info("Wrote %s", null_out)


if __name__ == "__main__":
    main()
