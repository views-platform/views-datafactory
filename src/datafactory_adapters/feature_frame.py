"""FeatureFrame — re-exported from views-frames v1.0.0.

The local FeatureFrame has been replaced by the canonical
views-frames implementation (#220). This module re-exports
to preserve the import path.
"""

from __future__ import annotations

from views_frames import (
    FeatureFrame,
    FrameMetadata,
    SpatialLevel,
    SpatioTemporalIndex,
)

REQUIRED_IDENTIFIERS: set[str] = {"time", "unit"}

__all__ = [
    "FeatureFrame",
    "FrameMetadata",
    "REQUIRED_IDENTIFIERS",
    "SpatialLevel",
    "SpatioTemporalIndex",
]
