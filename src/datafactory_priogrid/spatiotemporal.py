"""Composed spatiotemporal index backbone.

Holds a spatial GridConfig and a TemporalConfig. Lazily generates
the coordinate arrays. This is the index that downstream data cubes
align to.
"""

import functools
from dataclasses import dataclass, field

import numpy as np

from datafactory_priogrid.cell_generator import generate_grid
from datafactory_priogrid.grid_config import GridConfig
from datafactory_priogrid.temporal_config import TemporalConfig
from datafactory_priogrid.temporal_generator import generate_time_steps


@dataclass(frozen=True)
class SpatioTemporalGrid:
    """Spatiotemporal index composing a spatial grid and temporal range.

    Neither config is modified -- the grid composes them as peers.
    Coordinate arrays are generated lazily via cached_property.
    """

    grid_config: GridConfig = field(default_factory=GridConfig)
    temporal_config: TemporalConfig = field(default_factory=TemporalConfig)

    @property
    def n_cells(self) -> int:
        return self.grid_config.n_cells

    @property
    def n_steps(self) -> int:
        return self.temporal_config.n_steps

    @property
    def shape(self) -> tuple[int, int]:
        """(n_cells, n_steps) -- the index dimensions for a data cube."""
        return (self.n_cells, self.n_steps)

    @functools.cached_property
    def _spatial_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate spatial arrays once, cache the triple."""
        return generate_grid(self.grid_config)

    @property
    def pgids(self) -> np.ndarray:
        """1-D int32 array of PRIO-GRID cell IDs."""
        return self._spatial_arrays[0]

    @property
    def lats(self) -> np.ndarray:
        """1-D float64 array of cell centroid latitudes."""
        return self._spatial_arrays[1]

    @property
    def lons(self) -> np.ndarray:
        """1-D float64 array of cell centroid longitudes."""
        return self._spatial_arrays[2]

    @functools.cached_property
    def time_steps(self) -> np.ndarray:
        """1-D datetime64[M] array of monthly time steps."""
        return generate_time_steps(self.temporal_config)
