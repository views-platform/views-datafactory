"""GAUL 2024 administrative boundary harvester.

Downloads GAUL shapefiles from FAO and performs a spatial join
against PRIO-GRID cell centroids to produce a lookup table:
    pgid → (gaul0_code, gaul0_name, gaul1_code, gaul1_name,
            gaul2_code, gaul2_name, iso3_code)

Uses pyshp (already a dependency) to read shapefiles and shapely
STRtree for the spatial join. No geopandas.

Output: one Parquet file per admin variable (gaul0_code.parquet,
gaul1_code.parquet, etc.) with columns (gid, value), matching
the priogrid_static pattern.

Source: FAO GAUL 2024 (CC-BY-4.0)
    https://www.fao.org/agroinformatics/training-and-resources/
    data-sets/data-set-detail/global-gaul-new-2024-release/en
"""

from __future__ import annotations

import io
import json
import logging
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import requests
import shapefile as shp
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from datafactory_harvester.sources import register_source
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
    last_digest_for_version,
)

logger = logging.getLogger(__name__)

DATASET_ID = "gaul_admin"

# ---- FAO download URLs (CC-BY-4.0) ----

GAUL_L1_URL = (
    "https://storage.googleapis.com/fao-maps-catalog-data"
    "/boundaries/GAUL_2024_L1.zip"
)
GAUL_L2_URL = (
    "https://storage.googleapis.com/fao-maps-catalog-data"
    "/boundaries/GAUL_2024_L2.zip"
)

# L2 contains the full admin hierarchy so we use it as the
# primary join. L1 is fallback for centroids not matched by L2.
# GAUL 2024 DBF fields: gaul0_code, gaul0_name, gaul1_code,
# gaul1_name, gaul2_code, gaul2_name, iso3_code, map_code,
# continent, disp_en


# ---- Config ----


@dataclass(frozen=True)
class GaulAdminConfig:
    """Configuration for harvesting GAUL admin boundaries.

    Downloads GAUL 2024 shapefiles from FAO, performs spatial
    join against PRIO-GRID centroids, and stores per-variable
    Parquet files (gid, value) for grid assembly.
    """

    gaul_l1_url: str = GAUL_L1_URL
    gaul_l2_url: str = GAUL_L2_URL
    centroid_shapefile: Path = Path(
        "data/raw/priogrid/shapefile/priogrid_centroid.shp"
    )
    data_dir: Path = Path("data/raw/gaul_admin")
    cache_dir: Path = Path("data/raw/gaul_admin/shapefiles")
    ledger_path: Path = Path(
        "provenance/gaul_admin/ingestion_ledger.jsonl"
    )
    timeout: int = 300
    variables: tuple[str, ...] | None = field(default=None)

    def __post_init__(self) -> None:
        if self.timeout < 1:
            err_msg = (
                f"timeout must be >= 1, got {self.timeout}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)


# ---- Shapefile download ----


def _download_shapefile_zip(
    url: str,
    cache_dir: Path,
    *,
    timeout: int = 300,
) -> Path:
    """Download and extract a zipped shapefile.

    Local-first: skips download if .shp already exists.
    Returns path to the extracted .shp file.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Check if already extracted
    existing = list(cache_dir.glob("**/*.shp"))
    shp_candidates = [
        p for p in existing
        if p.stem in url.split("/")[-1].replace(".zip", "")
    ]
    if shp_candidates:
        logger.info("Shapefile cached: %s", shp_candidates[0])
        return shp_candidates[0]

    # Download
    logger.info("Downloading %s ...", url)
    t0 = time.monotonic()
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    # Read into memory and extract
    content = resp.content
    elapsed = time.monotonic() - t0
    size_mb = len(content) / 1e6
    logger.info(
        "Downloaded %.0f MB in %.1fs", size_mb, elapsed
    )

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        zf.extractall(cache_dir)
        logger.info(
            "Extracted %d files to %s",
            len(zf.namelist()), cache_dir,
        )

    # Find the .shp
    extracted = list(cache_dir.glob("**/*.shp"))
    if not extracted:
        msg = f"No .shp found after extracting {url}"
        raise FileNotFoundError(msg)

    return extracted[0]


# ---- Centroid loading ----


def _load_centroids(
    centroid_path: Path,
) -> list[tuple[int, float, float]]:
    """Load PRIO-GRID centroids from shapefile.

    Returns list of (gid, lon, lat) tuples.
    """
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


# ---- Spatial join ----


def _spatial_join(
    centroids: list[tuple[int, float, float]],
    shp_path: Path,
    field_names: list[str],
) -> dict[int, dict[str, object]]:
    """Join centroids against admin polygons.

    Uses shapely STRtree for O(log n) spatial indexing.

    Args:
        centroids: List of (gid, lon, lat).
        shp_path: Path to admin shapefile.
        field_names: DBF field names to extract per match.

    Returns:
        Dict mapping gid → {field_name: value, ...}.
    """
    # Read admin polygons
    logger.info("Reading %s ...", shp_path.name)
    polygons = []
    records = []
    with shp.Reader(str(shp_path)) as sf:
        dbf_fields = [f[0] for f in sf.fields[1:]]
        field_indices = []
        for fn in field_names:
            if fn not in dbf_fields:
                msg = (
                    f"Field {fn!r} not in shapefile. "
                    f"Available: {dbf_fields}"
                )
                raise ValueError(msg)
            field_indices.append(dbf_fields.index(fn))

        for sr in sf.iterShapeRecords():
            geo = sr.shape.__geo_interface__
            if geo["type"] == "Null":
                continue
            polygons.append(shape(geo))
            records.append(
                {fn: sr.record[idx]
                 for fn, idx in zip(
                     field_names, field_indices, strict=True
                 )}
            )

    logger.info(
        "Loaded %d admin polygons, building index...",
        len(polygons),
    )

    # Build spatial index
    tree = STRtree(polygons)

    # Join each centroid
    result: dict[int, dict[str, object]] = {}
    n_matched = 0
    n_unmatched = 0

    t0 = time.monotonic()
    for gid, lon, lat in centroids:
        pt = Point(lon, lat)
        indices = tree.query(pt, predicate="intersects")
        if len(indices) > 0:
            # Take first match (if multiple, nearest is fine
            # for 0.5° cells — admin boundaries don't overlap
            # within a single level)
            idx = int(indices[0])
            result[gid] = records[idx]
            n_matched += 1
        else:
            n_unmatched += 1

    elapsed = time.monotonic() - t0
    logger.info(
        "Spatial join: %d matched, %d unmatched (%.1fs)",
        n_matched, n_unmatched, elapsed,
    )
    return result


# ---- Variable extraction ----

# Each "variable" becomes a Parquet file (gid, value) matching
# the priogrid_static pattern.

ADMIN_VARIABLES: dict[str, dict[str, str]] = {
    "gaul0_code": {
        "level": "l2",
        "field": "gaul0_code",
        "display": "GAUL country code",
    },
    "gaul0_name": {
        "level": "l2",
        "field": "gaul0_name",
        "display": "GAUL country name",
    },
    "gaul1_code": {
        "level": "l2",
        "field": "gaul1_code",
        "display": "GAUL admin-1 code",
    },
    "gaul1_name": {
        "level": "l2",
        "field": "gaul1_name",
        "display": "GAUL admin-1 name",
    },
    "gaul2_code": {
        "level": "l2",
        "field": "gaul2_code",
        "display": "GAUL admin-2 code",
    },
    "gaul2_name": {
        "level": "l2",
        "field": "gaul2_name",
        "display": "GAUL admin-2 name",
    },
    "iso3_code": {
        "level": "l2",
        "field": "iso3_code",
        "display": "ISO 3166-1 alpha-3 country code",
    },
}

# L1 fallback fields — used for centroids not matched by L2
_L1_FALLBACK_FIELDS: dict[str, str] = {
    "gaul0_code": "gaul0_code",
    "gaul0_name": "gaul0_name",
    "gaul1_code": "gaul1_code",
    "gaul1_name": "gaul1_name",
    "iso3_code": "iso3_code",
}


def _write_variable(
    var_name: str,
    join_result: dict[int, dict[str, object]],
    field_name: str,
    config: GaulAdminConfig,
    *,
    is_numeric: bool,
    display_name: str,
    fallback: dict[int, dict[str, object]] | None = None,
    fallback_field: str | None = None,
) -> dict:
    """Write one admin variable as Parquet (gid, value).

    Returns a result dict matching the priogrid_static pattern.
    """
    snap_path = config.data_dir / f"{var_name}.parquet"

    gids: list[int] = []
    values_int: list[int] = []
    values_str: list[str] = []
    n_from_fallback = 0

    all_gids = sorted(
        set(join_result.keys())
        | (set(fallback.keys()) if fallback else set())
    )

    for gid in all_gids:
        rec = join_result.get(gid)
        val = rec[field_name] if rec and field_name in rec else None

        # Try fallback if primary didn't match
        if val is None and fallback and fallback_field:
            fb_rec = fallback.get(gid)
            if fb_rec and fallback_field in fb_rec:
                val = fb_rec[fallback_field]
                n_from_fallback += 1

        if val is None:
            continue

        gids.append(gid)
        if is_numeric:
            values_int.append(int(val))
        else:
            values_str.append(str(val))

    # Build table
    if is_numeric:
        table = pa.table({
            "gid": pa.array(gids, type=pa.int32()),
            "value": pa.array(values_int, type=pa.int32()),
        })
    else:
        table = pa.table({
            "gid": pa.array(gids, type=pa.int32()),
            "value": pa.array(values_str, type=pa.string()),
        })

    # Digest
    content = values_int if is_numeric else values_str
    content_bytes = json.dumps(
        list(zip(gids, content, strict=True)),
        sort_keys=True,
    ).encode()
    content_digest = compute_content_digest(content_bytes)

    # Check if unchanged
    previous = last_digest_for_version(
        config.ledger_path, var_name
    )
    if previous == content_digest:
        logger.info(
            "%s unchanged (digest: %s)", var_name, content_digest
        )
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": var_name,
            "n_cells": len(gids),
            "content_digest": content_digest,
            "outcome": "unchanged",
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
        return {
            "variable": var_name,
            "outcome": "unchanged",
            "digest": content_digest,
        }

    # Write
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, snap_path, compression="snappy")

    # Provenance
    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": var_name,
        "n_cells": len(gids),
        "n_from_fallback": n_from_fallback,
        "content_digest": content_digest,
        "variable_metadata": {
            "display_name": display_name,
            "category": "Administrative boundaries",
            "source": "FAO GAUL 2024",
            "license": "CC-BY-4.0",
        },
        "outcome": "success",
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "%s: %d cells, %d from L1 fallback, digest %s",
        var_name, len(gids), n_from_fallback, content_digest,
    )
    return {
        "variable": var_name,
        "outcome": "success",
        "n_cells": len(gids),
        "n_from_fallback": n_from_fallback,
        "digest": content_digest,
        "path": str(snap_path),
    }


# ---- Orchestrator ----


def fetch_gaul_admin(
    config: GaulAdminConfig | None = None,
    *,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch GAUL admin boundaries and join to PRIO-GRID.

    1. Download GAUL L2 and L1 shapefiles (cached locally)
    2. Load PRIO-GRID centroids
    3. Spatial join centroids against L2, then L1 as fallback
    4. Write per-variable Parquet files (gid, value)

    Returns list of per-variable result dicts.
    """
    if config is None:
        config = GaulAdminConfig()

    # Check for cached results (all variables present)
    if not force_refresh and config.variables is None:
        all_cached = all(
            (config.data_dir / f"{v}.parquet").exists()
            and last_digest_for_version(
                config.ledger_path, v
            ) is not None
            for v in ADMIN_VARIABLES
        )
        if all_cached:
            logger.info("All GAUL variables cached")
            return [
                {
                    "variable": v,
                    "outcome": "cached",
                    "digest": last_digest_for_version(
                        config.ledger_path, v
                    ),
                }
                for v in ADMIN_VARIABLES
            ]

    # Download shapefiles
    l2_shp = _download_shapefile_zip(
        config.gaul_l2_url,
        config.cache_dir / "GAUL_2024_L2",
        timeout=config.timeout,
    )
    l1_shp = _download_shapefile_zip(
        config.gaul_l1_url,
        config.cache_dir / "GAUL_2024_L1",
        timeout=config.timeout,
    )

    # Load centroids
    centroids = _load_centroids(config.centroid_shapefile)

    # Spatial join: L2 (primary)
    l2_fields = sorted({
        v["field"] for v in ADMIN_VARIABLES.values()
        if v["level"] == "l2"
    })
    logger.info("Spatial join against L2 (%s)...", l2_fields)
    l2_join = _spatial_join(centroids, l2_shp, l2_fields)

    # Spatial join: L1 (fallback for unmatched centroids)
    l1_fields = sorted(set(_L1_FALLBACK_FIELDS.values()))
    logger.info("Spatial join against L1 (%s)...", l1_fields)
    l1_join = _spatial_join(centroids, l1_shp, l1_fields)

    # Filter to requested variables
    variables = ADMIN_VARIABLES
    if config.variables is not None:
        requested = set(config.variables)
        variables = {
            k: v for k, v in ADMIN_VARIABLES.items()
            if k in requested
        }
        missing = requested - set(variables.keys())
        if missing:
            logger.warning(
                "Unknown variables: %s", sorted(missing)
            )

    # Write each variable
    results: list[dict] = []
    for var_name, var_meta in variables.items():
        is_numeric = (
            var_name.endswith("_code")
            and not var_name.startswith("iso")
        )
        fb_field = _L1_FALLBACK_FIELDS.get(var_name)
        try:
            result = _write_variable(
                var_name,
                l2_join,
                var_meta["field"],
                config,
                is_numeric=is_numeric,
                display_name=var_meta["display"],
                fallback=l1_join if fb_field else None,
                fallback_field=fb_field,
            )
            results.append(result)
        except Exception as exc:
            logger.error(
                "Failed to write %s: %s", var_name, exc
            )
            results.append({
                "variable": var_name,
                "outcome": "failed",
                "errors": [str(exc)],
            })

    return results


# Auto-register
register_source("gaul_admin", fetch_gaul_admin)
