"""PRIO-GRID spatial and temporal backbone.

Pure numpy. Zero external data dependencies for grid generation.
Shapefile used only for one-time parity validation.
"""

from datafactory_priogrid.cell_generator import (
    generate_bounding_boxes,
    generate_grid,
    latlon_to_pgid,
    pgid_to_latlon,
)
from datafactory_priogrid.grid_config import GridConfig
from datafactory_priogrid.parity_validation import (
    ParityResult,
    ReferenceGeometryReader,
    record_parity_result,
    validate_parity,
)
from datafactory_priogrid.shapefile_reader import PyShpReader
from datafactory_priogrid.spatiotemporal import SpatioTemporalGrid
from datafactory_priogrid.temporal_config import TemporalConfig
from datafactory_priogrid.temporal_generator import (
    from_views_month_id,
    generate_time_steps,
    to_views_month_id,
)
from datafactory_provenance.constants import VIEWS_EPOCH_YEAR

# harvester.fetch_shapefile is not imported here to avoid pulling
# 'requests' on every `import datafactory_priogrid`. Access it via:
#     from datafactory_priogrid.shapefile_harvester import fetch_shapefile

__all__ = [
    "GridConfig",
    "TemporalConfig",
    "VIEWS_EPOCH_YEAR",
    "SpatioTemporalGrid",
    "generate_grid",
    "generate_bounding_boxes",
    "generate_time_steps",
    "pgid_to_latlon",
    "latlon_to_pgid",
    "to_views_month_id",
    "from_views_month_id",
    "ReferenceGeometryReader",
    "ParityResult",
    "validate_parity",
    "record_parity_result",
    "PyShpReader",
]
