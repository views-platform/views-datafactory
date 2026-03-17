"""PRIO-GRID spatial backbone configuration.

Pure spatial parameters only. No storage paths, no remote URLs —
those are runtime concerns injected at call sites.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GridConfig:
    """Configuration for the PRIO-GRID spatial backbone.

    Default values reproduce the standard PRIO-GRID exactly:
    360 rows x 720 cols of 0.5 x 0.5 degree cells covering the full globe.

    The cell ID scheme is row-major from bottom-left:
        pgid = row_from_south * ncol + col_from_west + 1

    Cell centroids:
        lat = south + row_from_south * resolution + resolution / 2
        lon = west  + col_from_west  * resolution + resolution / 2

    Examples:
        Cell 1:      lat=-89.75, lon=-179.75  (Antarctic, date line)
        Cell 720:    lat=-89.75, lon= 179.75  (end of first row)
        Cell 721:    lat=-89.25, lon=-179.75  (second row)
        Cell 259200: lat= 89.75, lon= 179.75  (Arctic, east)

    Source: create_pg_indices() in
    https://github.com/prio-data/priogrid/blob/master/R/utility.R
    """

    # Spatial resolution in decimal degrees
    resolution: float = 0.5

    # Bounding box (WGS84)
    west: float = -180.0
    east: float = 180.0
    south: float = -90.0
    north: float = 90.0

    # CRS
    crs: str = "EPSG:4326"

    def __post_init__(self) -> None:
        if self.resolution <= 0:
            raise ValueError(f"Resolution must be positive, got {self.resolution}")
        if self.west >= self.east:
            raise ValueError(
                f"West bound ({self.west}) must be less than east ({self.east})"
            )
        if self.south >= self.north:
            raise ValueError(
                f"South bound ({self.south}) must be less than north ({self.north})"
            )
        lat_extent = self.north - self.south
        lon_extent = self.east - self.west
        nrow = lat_extent / self.resolution
        ncol = lon_extent / self.resolution
        if abs(nrow - round(nrow)) > 1e-9 or abs(ncol - round(ncol)) > 1e-9:
            raise ValueError(
                f"Resolution {self.resolution} does not evenly divide "
                f"lat extent ({lat_extent}) or lon extent ({lon_extent})"
            )

    # Derived grid dimensions (at default 0.5 deg: 360 x 720 = 259,200 cells)
    @property
    def nrow(self) -> int:
        return int((self.north - self.south) / self.resolution)

    @property
    def ncol(self) -> int:
        return int((self.east - self.west) / self.resolution)

    @property
    def n_cells(self) -> int:
        return self.nrow * self.ncol


DEFAULT_GRID_CONFIG = GridConfig()
