"""Grid array to FeatureFrame conversion.

Converts the canonical [T, H, W, C] grid output to a views-frames
`FeatureFrame` with a (month_id, priogrid_id) spatio-temporal index.

This is the frame-native path — numpy and views-frames only, no
pandas. It lived inside `grid_to_dataframe.py` until 2026-07-31,
which meant the future was physically inside the legacy module and
the pandas tier could not be deleted without surgery first (#379).
"""

from __future__ import annotations

import logging

import numpy as np

from datafactory_adapters._flatten import _flatten_grid
from datafactory_adapters.feature_frame import (
    FeatureFrame,
    FrameMetadata,
    SpatialLevel,
    SpatioTemporalIndex,
)

logger = logging.getLogger(__name__)

__all__ = ["grid_to_feature_frame"]


def grid_to_feature_frame(
    grid: np.ndarray,
    pgids: np.ndarray,
    time_steps: np.ndarray,
    feature_names: list[str],
    *,
    land_pgids: set[int] | None = None,
    month_id_epoch: int = 0,
    metadata: FrameMetadata | None = None,
) -> FeatureFrame:
    """Convert a [T, H, W, C] grid to a FeatureFrame.

    Args:
        grid: Grid array of shape [T, H, W, C].
        pgids: Cell ID array of shape [H, W].
        time_steps: Time array of shape [T] (datetime64[M]).
        feature_names: List of C feature column names.
        land_pgids: Optional set of land cell IDs for filtering.
        month_id_epoch: Base year for month_id encoding.
        metadata: Optional FrameMetadata for provenance.

    Returns:
        FeatureFrame with dense land-cell time series.
    """
    flat_data, all_month_ids, all_pgids = _flatten_grid(
        grid, pgids, time_steps, month_id_epoch, land_pgids
    )

    index = SpatioTemporalIndex(
        time=all_month_ids,
        unit=all_pgids.astype(np.int32),
        level=SpatialLevel.PGM,
    )
    return FeatureFrame.from_2d(
        y_features_2d=flat_data,
        index=index,
        feature_names=list(feature_names),
        metadata=metadata,
    )
