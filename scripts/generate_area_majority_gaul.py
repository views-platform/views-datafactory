#!/usr/bin/env python3
"""Generate area-majority GAUL assignments for all PRIO-GRID cells.

Usage:
    uv run python scripts/generate_area_majority_gaul.py
    uv run python scripts/generate_area_majority_gaul.py --data-dir data/raw/gaul_admin
    uv run python scripts/generate_area_majority_gaul.py --dry-run

Replaces centroid-in-polygon with area-majority spatial join:
for each 0.5° PRIO-GRID cell, assigns the GAUL polygon with the
largest intersection area. Recovers 9,481 coastal cells globally
whose centroids fall in water (C-149, ADR-039).

Produces seven Parquet files with (gid, value) schema:
    gaul0_code.parquet  — GAUL country code (int32)
    gaul1_code.parquet  — GAUL admin-1 code (int32)
    gaul2_code.parquet  — GAUL admin-2 code (int32)
    gaul0_name.parquet  — GAUL country name (utf8)
    gaul1_name.parquet  — GAUL admin-1 name (utf8)
    gaul2_name.parquet  — GAUL admin-2 name (utf8)
    iso3_code.parquet   — ISO 3166-1 alpha-3 code (utf8)

Dependencies: shapely 2.x, pyshp (both already installed).
No geopandas, no GDAL (ADR-030 compliance).

See: ADR-039, investigation #115, issue #118.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import shapefile as shp
from shapely import make_valid
from shapely.geometry import box as shapely_box
from shapely.geometry import shape
from shapely.strtree import STRtree

from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
)

logger = logging.getLogger(__name__)

DATASET_ID = "gaul_admin_area_majority"
_INT32 = pa.int32()
_UTF8 = pa.utf8()


def area_majority_join(
    cells: list[tuple[int, float, float]],
    gaul_polys: list,
    gaul_records: list[dict],
    field_name: str = "gaul0_code",
    *,
    default: int | str = -1,
) -> dict[int, int] | dict[int, str]:
    """Assign each cell to the GAUL polygon with the largest intersection area.

    Args:
        cells: List of (gid, centroid_lon, centroid_lat).
        gaul_polys: List of shapely Polygon/MultiPolygon geometries.
        gaul_records: List of dicts, one per polygon, containing field_name.
        field_name: Which GAUL field to extract (default: gaul0_code).
        default: Sentinel value for cells with no polygon overlap.

    Returns:
        Dict mapping gid → field value. Cells with no polygon
        overlap get the default sentinel.
    """
    if not cells:
        return {}

    valid_polys = [make_valid(p) for p in gaul_polys]
    tree = STRtree(valid_polys)

    result: dict[int, int] | dict[int, str] = {}
    for gid, lon, lat in cells:
        cell = shapely_box(lon - 0.25, lat - 0.25, lon + 0.25, lat + 0.25)
        indices = tree.query(cell, predicate="intersects")

        if len(indices) == 0:
            result[gid] = default
            continue

        if len(indices) == 1:
            idx = int(indices[0])
            area = cell.intersection(valid_polys[idx]).area
            if area > 0:
                result[gid] = gaul_records[idx][field_name]
            else:
                result[gid] = default
            continue

        best_code = default
        best_area = 0.0
        for idx in indices:
            idx = int(idx)
            area = cell.intersection(valid_polys[idx]).area
            if area > best_area:
                best_area = area
                best_code = gaul_records[idx][field_name]
            elif area == best_area and area > 0:
                candidate = gaul_records[idx][field_name]
                if type(best_code) is type(candidate):
                    best_code = min(best_code, candidate)
                elif best_code is default:
                    best_code = candidate

        result[gid] = best_code

    return result


def _compute_cell_polygon_map(
    cells: list[tuple[int, float, float]],
    gaul_polys: list,
) -> dict[int, int]:
    """Map each cell to the polygon index with the largest intersection area.

    Returns:
        Dict mapping gid → polygon index. Cells with no overlap get -1.
        Ties broken by lowest polygon index (deterministic, field-independent).
    """
    if not cells:
        return {}

    valid_polys = [make_valid(p) for p in gaul_polys]
    tree = STRtree(valid_polys)

    result: dict[int, int] = {}
    for gid, lon, lat in cells:
        cell = shapely_box(lon - 0.25, lat - 0.25, lon + 0.25, lat + 0.25)
        indices = tree.query(cell, predicate="intersects")

        if len(indices) == 0:
            result[gid] = -1
            continue

        if len(indices) == 1:
            idx = int(indices[0])
            area = cell.intersection(valid_polys[idx]).area
            result[gid] = idx if area > 0 else -1
            continue

        best_idx = -1
        best_area = 0.0
        for idx in indices:
            idx = int(idx)
            area = cell.intersection(valid_polys[idx]).area
            if area > best_area:
                best_area = area
                best_idx = idx
            elif area == best_area and area > 0 and idx < best_idx:
                best_idx = idx

        result[gid] = best_idx

    return result


def _load_gaul_polygons(
    shp_path: Path,
    field_names: list[str],
) -> tuple[list, list[dict]]:
    """Load GAUL polygons and records from a shapefile."""
    polygons = []
    records = []
    with shp.Reader(str(shp_path)) as sf:
        dbf_fields = [f[0] for f in sf.fields[1:]]
        field_indices = []
        for fn in field_names:
            if fn not in dbf_fields:
                msg = f"Field {fn!r} not in shapefile. Available: {dbf_fields}"
                raise ValueError(msg)
            field_indices.append(dbf_fields.index(fn))

        for sr in sf.iterShapeRecords():
            geo = sr.shape.__geo_interface__
            if geo["type"] == "Null":
                continue
            polygons.append(shape(geo))
            records.append(
                {fn: sr.record[idx]
                 for fn, idx in zip(field_names, field_indices, strict=True)}
            )

    logger.info("Loaded %d GAUL polygons from %s", len(polygons), shp_path.name)
    return polygons, records


def _load_centroids(centroid_path: Path) -> list[tuple[int, float, float]]:
    """Load PRIO-GRID centroids from shapefile."""
    if not centroid_path.exists():
        msg = f"Centroid shapefile not found: {centroid_path}"
        raise FileNotFoundError(msg)

    centroids: list[tuple[int, float, float]] = []
    with shp.Reader(str(centroid_path)) as sf:
        fields = [f[0] for f in sf.fields[1:]]
        gid_idx = fields.index("gid")
        for sr in sf.iterShapeRecords():
            gid = int(sr.record[gid_idx])
            lon, lat = sr.shape.points[0]
            centroids.append((gid, lon, lat))

    logger.info("Loaded %d centroids", len(centroids))
    return centroids


def _write_area_majority_parquet(
    var_name: str,
    assignments: dict[int, int] | dict[int, str],
    data_dir: Path,
    ledger_path: Path,
    *,
    dtype: pa.DataType = _INT32,
    method: str = "area_majority",
    gaul_version: str = "GAUL_2024",
) -> dict:
    """Write area-majority assignments as Parquet (gid, value)."""
    snap_path = data_dir / f"{var_name}.parquet"

    gids = sorted(assignments.keys())
    values = [assignments[gid] for gid in gids]

    table = pa.table({
        "gid": pa.array(gids, type=pa.int32()),
        "value": pa.array(values, type=dtype),
    })

    content_bytes = json.dumps(
        list(zip(gids, values, strict=True)),
        sort_keys=True,
    ).encode()
    content_digest = compute_content_digest(content_bytes)

    snap_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, snap_path, compression="snappy")

    if pa.types.is_integer(dtype):
        n_valid = sum(1 for v in values if v > 0)
        n_unassigned = sum(1 for v in values if v == -1)
    else:
        n_valid = sum(1 for v in values if v)
        n_unassigned = sum(1 for v in values if not v)

    append_ledger_entry(ledger_path, {
        "dataset": DATASET_ID,
        "version": var_name,
        "method": method,
        "gaul_version": gaul_version,
        "n_cells": len(gids),
        "n_valid": n_valid,
        "n_unassigned": n_unassigned,
        "content_digest": content_digest,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "%s: %d cells (%d valid, %d unassigned), digest=%s",
        var_name, len(gids), n_valid, n_unassigned, content_digest,
    )
    return {
        "variable": var_name,
        "n_cells": len(gids),
        "n_valid": n_valid,
        "n_unassigned": n_unassigned,
        "digest": content_digest,
    }


def _load_supplement_polygons(
    geojson_path: Path,
    field_names: list[str],
) -> tuple[list, list[dict]]:
    """Load supplement polygons from a GeoJSON file."""
    data = json.loads(geojson_path.read_text())
    polygons = []
    records = []
    for feature in data["features"]:
        geom = shape(feature["geometry"])
        polygons.append(geom)
        props = feature["properties"]
        records.append({fn: props[fn] for fn in field_names})

    logger.info(
        "Loaded %d supplement polygons from %s",
        len(polygons), geojson_path.name,
    )
    return polygons, records


def _filter_covered_supplements(
    gaul_polys: list,
    sup_polys: list,
    sup_recs: list[dict],
    *,
    coverage_threshold: float = 0.5,
) -> tuple[list, list[dict]]:
    """Filter supplement polygons already covered by GAUL.

    Returns (kept_polys, kept_recs) — only supplements where no GAUL
    polygon covers more than ``coverage_threshold`` of their area.
    """
    gaul_tree = STRtree([make_valid(p) for p in gaul_polys])
    kept_polys = []
    kept_recs = []
    for poly, rec in zip(sup_polys, sup_recs, strict=True):
        hits = gaul_tree.query(poly, predicate="intersects")
        covered = any(
            make_valid(gaul_polys[int(i)]).intersection(poly).area
            / poly.area > coverage_threshold
            for i in hits
        )
        if covered:
            logger.warning(
                "Supplement %s skipped — GAUL already covers it "
                "(source defect likely fixed)",
                rec.get("gaul1_name", "unknown"),
            )
        else:
            kept_polys.append(poly)
            kept_recs.append(rec)
    return kept_polys, kept_recs


GAUL_CODE_VARIABLES = [
    ("gaul0_code", ["gaul0_code"]),
    ("gaul1_code", ["gaul1_code"]),
    ("gaul2_code", ["gaul2_code"]),
]

GAUL_NAME_VARIABLES = [
    ("gaul0_name", ["gaul0_name"]),
    ("gaul1_name", ["gaul1_name"]),
    ("gaul2_name", ["gaul2_name"]),
    ("iso3_code", ["iso3_code"]),
]


def main(
    data_dir: Path = Path("data/raw/gaul_admin"),
    cache_dir: Path = Path("data/raw/gaul_admin/shapefiles"),
    centroid_path: Path = Path(
        "data/raw/priogrid/shapefile/priogrid_centroid.shp"
    ),
    ledger_path: Path = Path(
        "provenance/gaul_admin/ingestion_ledger.jsonl"
    ),
    supplement_path: Path | None = None,
    *,
    dry_run: bool = False,
) -> list[dict]:
    """Generate area-majority GAUL assignments for all PRIO-GRID cells."""
    l2_shp = list(cache_dir.glob("**/GAUL_2024_L2*.shp"))
    if not l2_shp:
        msg = f"No GAUL L2 shapefile in {cache_dir}. Run harvest_gaul.py first."
        raise FileNotFoundError(msg)
    l2_shp_path = l2_shp[0]

    centroids = _load_centroids(centroid_path)

    all_field_names = [f for _, fields in GAUL_CODE_VARIABLES + GAUL_NAME_VARIABLES
                       for f in fields]
    polygons, records = _load_gaul_polygons(l2_shp_path, all_field_names)

    if supplement_path is not None:
        if not supplement_path.exists():
            msg = f"Supplement file not found: {supplement_path}"
            raise FileNotFoundError(msg)
        sup_polys, sup_recs = _load_supplement_polygons(
            supplement_path, all_field_names,
        )
        kept_polys, kept_recs = _filter_covered_supplements(
            polygons, sup_polys, sup_recs,
        )
        if kept_polys:
            polygons.extend(kept_polys)
            records.extend(kept_recs)
            logger.info("Appended %d supplement polygons", len(kept_polys))
        elif sup_polys:
            logger.warning(
                "All %d supplement polygons skipped — GAUL now covers "
                "them. Consider retiring the supplement (ADR-043).",
                len(sup_polys),
            )

    t0 = time.monotonic()
    cell_poly_map = _compute_cell_polygon_map(centroids, polygons)
    elapsed = time.monotonic() - t0
    rate = len(centroids) / elapsed
    logger.info(
        "Area-majority join: %d cells, %.1fs (%.0f cells/sec)",
        len(centroids), elapsed, rate,
    )

    results = []

    all_variables = [
        (var_name, fields[0], _INT32, -1)
        for var_name, fields in GAUL_CODE_VARIABLES
    ] + [
        (var_name, fields[0], _UTF8, "")
        for var_name, fields in GAUL_NAME_VARIABLES
    ]

    for var_name, field_name, dtype, default in all_variables:
        assignments: dict[int, int] | dict[int, str] = {}
        for gid, poly_idx in cell_poly_map.items():
            if poly_idx == -1:
                assignments[gid] = default
            else:
                assignments[gid] = records[poly_idx][field_name]

        if dry_run:
            if pa.types.is_integer(dtype):
                n_valid = sum(1 for v in assignments.values() if v > 0)
            else:
                n_valid = sum(1 for v in assignments.values() if v)
            logger.info(
                "[DRY RUN] %s: %d valid, %d unassigned",
                var_name, n_valid, len(assignments) - n_valid,
            )
            results.append({
                "variable": var_name,
                "n_cells": len(assignments),
                "dry_run": True,
            })
        else:
            result = _write_area_majority_parquet(
                var_name, assignments, data_dir, ledger_path,
                dtype=dtype,
            )
            results.append(result)

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path("data/raw/gaul_admin"),
    )
    parser.add_argument(
        "--cache-dir", type=Path,
        default=Path("data/raw/gaul_admin/shapefiles"),
    )
    parser.add_argument(
        "--centroid-path", type=Path,
        default=Path("data/raw/priogrid/shapefile/priogrid_centroid.shp"),
    )
    parser.add_argument(
        "--ledger-path", type=Path,
        default=Path("provenance/gaul_admin/ingestion_ledger.jsonl"),
    )
    parser.add_argument(
        "--supplement", type=Path, default=None,
        help="GeoJSON supplement for missing GAUL polygons",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute but don't write files",
    )
    args = parser.parse_args()

    results = main(
        data_dir=args.data_dir,
        cache_dir=args.cache_dir,
        centroid_path=args.centroid_path,
        ledger_path=args.ledger_path,
        supplement_path=args.supplement,
        dry_run=args.dry_run,
    )

    for r in results:
        print(json.dumps(r))
