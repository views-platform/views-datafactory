"""Grid flattening primitives — shared, pandas-free.

`_flatten_grid` turns a canonical [T, H, W, C] grid into (N, C) rows
plus aligned month_id / pgid index arrays. Every adapter starts here:
`grid_to_dataframe`, `grid_to_feature_frame`, `grid_to_country_month`.

Lives in its own module because it belongs to none of them. Until
2026-07-31 it squatted in `grid_to_dataframe.py` and
`grid_to_country_month.py` reached across for the private name — a
shared primitive with no home of its own.

numpy only: nothing here knows about pandas or views-frames.
"""

from __future__ import annotations

import numpy as np


def _compute_month_ids(
    time_steps: np.ndarray,
    epoch: int = 0,
) -> np.ndarray:
    """Convert datetime64[M] to integer month_ids.

    Args:
        time_steps: Array of datetime64[M] values.
        epoch: Base year for month_id computation.
            0 = raw (year*12 + month).
            1980 = VIEWS convention ((year-1980)*12 + month).

    Returns:
        Integer array of month_ids.
    """
    months_since_epoch_70 = time_steps.astype(
        "datetime64[M]"
    ).astype(int)
    years = 1970 + months_since_epoch_70 // 12
    months = months_since_epoch_70 % 12 + 1
    result: np.ndarray = (years - epoch) * 12 + months
    return result


def _flatten_grid(
    grid: np.ndarray,
    pgids: np.ndarray,
    time_steps: np.ndarray,
    month_id_epoch: int = 0,
    land_pgids: set[int] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Flatten [T, H, W, C] grid to (N, C) with index arrays.

    Shared by grid_to_dataframe, grid_to_feature_frame and
    grid_to_country_month.

    Returns:
        (flat_data, all_month_ids, all_pgids) — each of length N.

    Raises:
        ValueError: If grid is not 4D, pgids is not 2D, or
            spatial dimensions don't match.
    """
    from datafactory_adapters._validation import validate_grid_pgids

    validate_grid_pgids(grid, pgids)
    n_t, n_h, n_w, _ = grid.shape
    month_ids = _compute_month_ids(time_steps, month_id_epoch)

    flat_data: np.ndarray = grid.reshape(n_t * n_h * n_w, -1)
    pgids_flat = pgids.ravel()
    all_pgids = np.tile(pgids_flat, n_t)
    all_month_ids = np.repeat(month_ids, n_h * n_w)

    if land_pgids is not None:
        mask = np.isin(all_pgids, list(land_pgids))
        flat_data = flat_data[mask]
        all_pgids = all_pgids[mask]
        all_month_ids = all_month_ids[mask]

    return flat_data, all_month_ids, all_pgids
