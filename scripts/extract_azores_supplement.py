#!/usr/bin/env python3
"""Extract missing Azorean island polygons from Natural Earth.

FAO GAUL 2024 is missing 4 of 9 Azorean islands (São Miguel,
Santa Maria, Flores, Corvo) from both L1 and L2. This script
extracts those 4 polygons from Natural Earth 10m admin-1 and
writes a supplemental GeoJSON for use with the area-majority
generation script.

One-time script kept for reproducibility. The output GeoJSON
is committed to the repo.

Usage:
    uv run python scripts/extract_azores_supplement.py
"""

from __future__ import annotations

import json
import logging
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

import shapefile as shp
from shapely.geometry import mapping, shape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

NE_URL = (
    "https://naciscdn.org/naturalearth/10m/cultural/"
    "ne_10m_admin_1_states_provinces.zip"
)
NE_CACHE = Path(
    "data/raw/gaul_admin/shapefiles/ne_10m_admin_1"
)
OUTPUT = Path("data/raw/gaul_admin/supplement_azores.geojson")

ISLAND_MAP = {
    0: {
        "name": "Ilha de Santa Maria",
        "gaul1_code": -3728,
    },
    1: {
        "name": "Ilha de São Miguel",
        "gaul1_code": -3727,
    },
    7: {
        "name": "Ilha das Flores",
        "gaul1_code": -3729,
    },
    8: {
        "name": "Ilha do Corvo",
        "gaul1_code": -3730,
    },
}


def _ensure_natural_earth() -> Path:
    """Download Natural Earth 10m admin-1 if not cached."""
    shp_files = list(NE_CACHE.glob("*.shp"))
    if shp_files:
        logger.info("Using cached Natural Earth at %s", NE_CACHE)
        return shp_files[0]

    logger.info("Downloading Natural Earth 10m admin-1...")
    data = urllib.request.urlopen(NE_URL).read()
    logger.info("Downloaded %.1f MB", len(data) / 1e6)

    NE_CACHE.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        zf.extractall(NE_CACHE)

    shp_files = list(NE_CACHE.glob("*.shp"))
    if not shp_files:
        msg = f"No .shp found in {NE_CACHE}"
        raise FileNotFoundError(msg)
    return shp_files[0]


def _find_azores(shp_path: Path) -> list:
    """Find Azores MultiPolygon and decompose into islands."""
    with shp.Reader(str(shp_path)) as sf:
        fields = [f[0] for f in sf.fields[1:]]
        name_idx = fields.index("name")
        iso_idx = fields.index("iso_a2")

        for sr in sf.iterShapeRecords():
            if (
                sr.record[iso_idx] == "PT"
                and sr.record[name_idx] == "Azores"
            ):
                geom = shape(sr.shape.__geo_interface__)
                return list(geom.geoms)

    msg = "Azores not found in Natural Earth"
    raise ValueError(msg)


def main() -> None:
    shp_path = _ensure_natural_earth()
    islands = _find_azores(shp_path)
    logger.info("Azores: %d sub-polygons", len(islands))

    features = []
    for idx, meta in sorted(ISLAND_MAP.items()):
        poly = islands[idx]
        bounds = [round(b, 3) for b in poly.bounds]
        logger.info(
            "  %s: bounds=%s area=%.6f",
            meta["name"], bounds, poly.area,
        )
        features.append({
            "type": "Feature",
            "properties": {
                "gaul0_code": 325,
                "gaul0_name": "Portugal",
                "gaul1_code": meta["gaul1_code"],
                "gaul1_name": meta["name"],
                "gaul2_code": meta["gaul1_code"],
                "gaul2_name": meta["name"],
                "iso3_code": "PRT",
                "source": "natural_earth_10m_supplement",
            },
            "geometry": mapping(poly),
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(geojson, indent=2))
    logger.info("Wrote %s (%d features)", OUTPUT, len(features))


if __name__ == "__main__":
    main()
