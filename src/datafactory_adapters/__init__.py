"""Consumer-facing adapters for datafactory outputs.

Converts canonical [T, H, W, C] grid arrays to transport
formats: DataFrames, FeatureFrames, etc.

One concept per module (#379), split along the line that matters —
the legacy pandas tier versus the frame-native path:

- ``_flatten`` — shared numpy primitive, used by all three converters
- ``grid_to_feature_frame`` — frame-native (views-frames), pandas-free
- ``grid_to_dataframe`` / ``grid_to_country_month`` — the pandas tier,
  which needs the ``views-datafactory[pandas]`` extra

Dependencies are minimal: numpy and views-frames, plus pandas behind
the optional extra. No other ``datafactory_*`` imports.

Relocating this package into views-pipeline-core was considered and
**rejected** in 2026-07-31's review: it would break the published
ADR-050 consumer contract, and ``grid_to_country_month`` encodes
ADR-040 conservation and ADR-048 aggregation semantics that belong
beside the source registry declaring them. See the ``D-`` entry in
the risk register. The end state for the pandas tier is deletion,
not relocation — which the module split above makes cheap.
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
from datafactory_adapters.grid_to_dataframe import grid_to_dataframe
from datafactory_adapters.grid_to_feature_frame import (
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
