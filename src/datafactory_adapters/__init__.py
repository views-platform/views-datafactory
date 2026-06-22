"""Consumer-facing adapters for datafactory outputs.

Converts canonical [T, H, W, C] grid arrays to transport
formats: DataFrames, FeatureFrames, etc.

Designed to be extractable: this module may move to
views-pipeline-core or a dedicated micro-service when the
adapter pattern matures. Dependencies are minimal (numpy,
pandas only — no other datafactory_* imports).
"""

from datafactory_adapters.feature_frame import (
    FeatureFrame,
    FrameMetadata,
    SpatialLevel,
    SpatioTemporalIndex,
)
from datafactory_adapters.grid_from_feature_frame import (
    feature_frame_to_grid,
)
from datafactory_adapters.grid_to_country_month import (
    grid_to_country_month,
)
from datafactory_adapters.grid_to_dataframe import (
    grid_to_dataframe,
    grid_to_feature_frame,
)

__all__ = [
    "FeatureFrame",
    "FrameMetadata",
    "SpatialLevel",
    "SpatioTemporalIndex",
    "feature_frame_to_grid",
    "grid_to_country_month",
    "grid_to_dataframe",
    "grid_to_feature_frame",
]
