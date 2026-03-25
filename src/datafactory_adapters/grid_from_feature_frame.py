"""FeatureFrame to grid array reconstruction.

Inverse of grid_to_feature_frame: takes a FeatureFrame with
(time, unit) identifiers and reconstructs the canonical
[T, H, W, F] grid array using a pgids lookup.

Designed to be extractable: depends only on numpy.
"""

from __future__ import annotations

import logging

import numpy as np

from datafactory_adapters.feature_frame import FeatureFrame

logger = logging.getLogger(__name__)


def feature_frame_to_grid(
    ff: FeatureFrame,
    pgids: np.ndarray,
) -> np.ndarray:
    """Reconstruct a [T, H, W, F] grid from a FeatureFrame.

    Args:
        ff: FeatureFrame with identifiers 'time' (month_ids)
            and 'unit' (priogrid_gid values).
        pgids: Cell ID array of shape [H, W] used to map
            unit values back to (row, col) positions.

    Returns:
        np.ndarray of shape [T, H, W, F] with dtype float32.
        Cells not present in the FeatureFrame are set to 0.0.
    """
    if pgids.ndim != 2:
        msg = f"pgids must be 2D [H, W], got {pgids.ndim}D"
        raise ValueError(msg)
    n_h, n_w = pgids.shape
    n_f = ff.n_features

    month_ids = ff.identifiers["time"]
    unit_ids = ff.identifiers["unit"]
    data = ff.y_features  # (N, F)

    # Determine T from unique month_ids, preserving order
    unique_months = np.unique(month_ids)
    n_t = len(unique_months)
    month_to_t: dict[int, int] = {
        int(m): i for i, m in enumerate(unique_months)
    }

    # Build pgid → (row, col) lookup
    pgid_to_rc: dict[int, tuple[int, int]] = {}
    for r in range(n_h):
        for c in range(n_w):
            pgid_to_rc[int(pgids[r, c])] = (r, c)

    # Allocate output
    grid = np.zeros((n_t, n_h, n_w, n_f), dtype=np.float32)

    # Place each row
    n_placed = 0
    n_skipped = 0
    for i in range(len(month_ids)):
        mid = int(month_ids[i])
        uid = int(unit_ids[i])

        t = month_to_t.get(mid)
        rc = pgid_to_rc.get(uid)

        if t is not None and rc is not None:
            r, c = rc
            grid[t, r, c, :] = data[i]
            n_placed += 1
        else:
            n_skipped += 1

    logger.info(
        "Reconstructed [%d, %d, %d, %d]: %d placed, %d skipped",
        n_t, n_h, n_w, n_f, n_placed, n_skipped,
    )
    return grid
