"""Concrete shapefile readers for parity validation.

Each reader implements the ReferenceGeometryReader protocol defined in
validation.py. This module is the only place in datafactory_priogrid that
imports a shapefile library -- everything else stays dependency-free.

Current reader: PyShpReader (uses the pure-Python 'pyshp' package).
"""

import logging
from pathlib import Path

import shapefile  # pyshp

logger = logging.getLogger(__name__)

# Known PRIO-GRID attribute field names (case-insensitive matching)
_ID_NAMES = {"gid", "pgid", "priogrid_gid", "cell_id"}
_LAT_NAMES = {"ycoord", "lat", "latitude", "y"}
_LON_NAMES = {"xcoord", "lon", "longitude", "x"}


def _find_field(fields: list[str], candidates: set[str]) -> str | None:
    """Find the first field name matching any candidate (case-insensitive)."""
    lower_map = {f.lower(): f for f in fields}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


class PyShpReader:
    """Read PRIO-GRID centroids from a shapefile using pyshp.

    Expects the shapefile to contain attribute fields for cell ID,
    latitude, and longitude (e.g. gid, ycoord, xcoord). Field names
    are discovered automatically.

    If centroid coordinate fields are absent, falls back to computing
    centroids from polygon bounding boxes.
    """

    def read(self, path: Path) -> list[tuple[int, float, float]]:
        """Read reference centroids from a PRIO-GRID shapefile.

        Args:
            path: Path to a .shp file or a directory containing one.

        Returns:
            List of (pgid, centroid_lat, centroid_lon) tuples.
        """
        shp_path = self._resolve_shp(path)
        logger.info("Reading shapefile: %s", shp_path)

        with shapefile.Reader(str(shp_path)) as sf:
            # Field names (skip the DeletionFlag field at index 0)
            field_names = [f[0] for f in sf.fields[1:]]
            logger.info("Shapefile fields: %s", field_names)

            id_field = _find_field(field_names, _ID_NAMES)
            lat_field = _find_field(field_names, _LAT_NAMES)
            lon_field = _find_field(field_names, _LON_NAMES)

            if id_field is None:
                err_msg = (
                    f"No cell ID field found in {field_names}. "
                    f"Expected one of: {_ID_NAMES}"
                )
                logger.error(err_msg)
                raise ValueError(err_msg)

            use_geometry = lat_field is None or lon_field is None
            if use_geometry:
                logger.warning(
                    "Centroid fields not found (lat=%s, lon=%s). "
                    "Falling back to bounding-box centroids.",
                    lat_field,
                    lon_field,
                )
            else:
                logger.info(
                    "Using fields: id=%s, lat=%s, lon=%s",
                    id_field,
                    lat_field,
                    lon_field,
                )

            cells: list[tuple[int, float, float]] = []

            for sr in sf.iterShapeRecords():
                rec = sr.record
                gid = int(rec[id_field])

                if use_geometry:
                    bbox = sr.shape.bbox  # (min_x, min_y, max_x, max_y)
                    lon = (bbox[0] + bbox[2]) / 2
                    lat = (bbox[1] + bbox[3]) / 2
                else:
                    lat = float(rec[lat_field])
                    lon = float(rec[lon_field])

                cells.append((gid, lat, lon))

        logger.info("Read %d cells from shapefile", len(cells))
        return cells

    @staticmethod
    def _resolve_shp(path: Path) -> Path:
        """Resolve path to the actual .shp file."""
        if path.is_file() and path.suffix.lower() == ".shp":
            return path

        if path.is_dir():
            shp_files = list(path.glob("*.shp"))
            if len(shp_files) == 1:
                return shp_files[0]
            if len(shp_files) > 1:
                # Prefer the one named 'priogrid'
                for f in shp_files:
                    if "priogrid" in f.stem.lower():
                        return f
                return shp_files[0]
            raise FileNotFoundError(f"No .shp file found in {path}")

        raise FileNotFoundError(f"Not a file or directory: {path}")
