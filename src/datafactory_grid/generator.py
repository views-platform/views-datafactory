"""Programmatic PRIO-GRID generator -- pure numpy, zero external data dependency.

Generates a full 360x720 global grid with cell IDs matching PRIO-GRID's
numbering scheme. Returns plain numpy arrays. No geometry libraries.
"""

import logging

import numpy as np

from datafactory_grid.config import DEFAULT_GRID_CONFIG, GridConfig

logger = logging.getLogger(__name__)


def generate_grid(
    config: GridConfig = DEFAULT_GRID_CONFIG,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate cell IDs and centroid coordinates for the full grid.

    Returns:
        (pgids, lats, lons) -- three 1-D arrays of length config.n_cells.
        pgids are 1-based int32 matching PRIO-GRID's numbering.
        lats/lons are float64 cell centroids in decimal degrees.
    """

    nrow, ncol = config.nrow, config.ncol
    half = config.resolution / 2

    # Row-major from bottom-left: pgid = row_from_south * ncol + col + 1
    rows = np.repeat(np.arange(nrow), ncol)
    cols = np.tile(np.arange(ncol), nrow)

    pgids = (rows * ncol + cols + 1).astype(np.int32)
    lats = (config.south + rows * config.resolution + half).astype(np.float64)
    lons = (config.west + cols * config.resolution + half).astype(np.float64)

    logger.info(
        "Generated %d centroids (%.2f deg grid, %dx%d)",
        len(pgids),
        config.resolution,
        nrow,
        ncol,
    )
    return pgids, lats, lons


def generate_bounding_boxes(
    config: GridConfig = DEFAULT_GRID_CONFIG,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate cell IDs and bounding boxes for the full grid.

    Returns:
        (pgids, west, south, east, north) -- five 1-D arrays.
        Each cell's bounding box is (west, south, east, north) in degrees.
    """

    pgids, lats, lons = generate_grid(config)
    half = config.resolution / 2

    return (
        pgids,
        lons - half,  # west
        lats - half,  # south
        lons + half,  # east
        lats + half,  # north
    )


def pgid_to_latlon(
    pgid: int | np.ndarray,
    config: GridConfig = DEFAULT_GRID_CONFIG,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert cell ID(s) to centroid (lat, lon).

    Works for scalar or array input. Returns float64 arrays.

    Raises:
        ValueError: If any pgid is outside [1, config.n_cells].
    """
    pgid = np.asarray(pgid, dtype=np.int32)
    if np.any(pgid < 1) or np.any(pgid > config.n_cells):
        err_msg = (
            f"pgid must be in [1, {config.n_cells}], "
            f"got range [{int(pgid.min())}, {int(pgid.max())}]"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)
    idx = pgid - 1
    rows = idx // config.ncol
    cols = idx % config.ncol
    half = config.resolution / 2

    lats = (config.south + rows * config.resolution + half).astype(np.float64)
    lons = (config.west + cols * config.resolution + half).astype(np.float64)
    return lats, lons


def latlon_to_pgid(
    lat: float | np.ndarray,
    lon: float | np.ndarray,
    config: GridConfig = DEFAULT_GRID_CONFIG,
) -> np.ndarray:
    """Convert (lat, lon) coordinates to the enclosing cell ID(s).

    Points exactly on a cell boundary are assigned to the cell
    to the north/east (matching standard raster convention).
    """

    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)

    rows = np.floor((lat - config.south) / config.resolution).astype(np.int32)
    cols = np.floor((lon - config.west) / config.resolution).astype(np.int32)

    # Clamp to valid range
    rows = np.clip(rows, 0, config.nrow - 1)
    cols = np.clip(cols, 0, config.ncol - 1)

    return (rows * config.ncol + cols + 1).astype(np.int32)
