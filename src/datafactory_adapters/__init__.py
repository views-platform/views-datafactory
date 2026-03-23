"""Consumer-facing adapters for datafactory outputs.

Converts canonical [T, H, W, C] grid arrays to transport
formats: DataFrames, FeatureFrames, etc.

Designed to be extractable: this module may move to
views-pipeline-core or a dedicated micro-service when the
adapter pattern matures. Dependencies are minimal (numpy,
pandas only — no other datafactory_* imports).
"""

from datafactory_adapters.feature_frame import FeatureFrame
from datafactory_adapters.grid_to_dataframe import (
    grid_to_dataframe,
    grid_to_feature_frame,
)

__all__ = [
    "FeatureFrame",
    "grid_to_dataframe",
    "grid_to_feature_frame",
]
