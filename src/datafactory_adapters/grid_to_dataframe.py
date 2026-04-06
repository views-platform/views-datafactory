"""Grid array to DataFrame conversion.

Converts the canonical [T, H, W, C] grid output to a pandas
DataFrame with (month_id, priogrid_gid) MultiIndex. Supports
land filtering and configurable month_id encoding.

Designed to be extractable: depends only on numpy + pandas.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from datafactory_adapters.feature_frame import FeatureFrame

logger = logging.getLogger(__name__)


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

    Shared by grid_to_dataframe and grid_to_feature_frame.

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


def grid_to_dataframe(
    grid: np.ndarray,
    pgids: np.ndarray,
    time_steps: np.ndarray,
    feature_names: list[str],
    *,
    land_pgids: set[int] | None = None,
    month_id_epoch: int = 0,
    sparse: bool = False,
) -> pd.DataFrame:
    """Convert a [T, H, W, C] grid to a DataFrame.

    Args:
        grid: Grid array of shape [T, H, W, C].
        pgids: Cell ID array of shape [H, W].
        time_steps: Time array of shape [T] (datetime64[M]).
        feature_names: List of C feature column names.
        land_pgids: Optional set of land cell IDs. If provided,
            only land cells are included (dense). If None, all
            cells are included.
        month_id_epoch: Base year for month_id encoding.
            0 = year*12+month. 1980 = VIEWS convention.
        sparse: If True, keep only non-zero rows. If False
            (default), keep all rows (dense time series).

    Returns:
        DataFrame with (month_id, priogrid_gid) MultiIndex
        and one column per feature.
    """
    flat_data, all_month_ids, all_pgids = _flatten_grid(
        grid, pgids, time_steps, month_id_epoch, land_pgids
    )

    if sparse:
        nonzero = flat_data.any(axis=1)
        flat_data = flat_data[nonzero]
        all_pgids = all_pgids[nonzero]
        all_month_ids = all_month_ids[nonzero]

    index = pd.MultiIndex.from_arrays(
        [all_month_ids, all_pgids],
        names=["month_id", "priogrid_gid"],
    )
    df = pd.DataFrame(
        flat_data, index=index, columns=feature_names
    )
    return df.sort_index()


def grid_to_feature_frame(
    grid: np.ndarray,
    pgids: np.ndarray,
    time_steps: np.ndarray,
    feature_names: list[str],
    *,
    land_pgids: set[int] | None = None,
    month_id_epoch: int = 0,
    metadata: dict | None = None,
) -> FeatureFrame:
    """Convert a [T, H, W, C] grid to a FeatureFrame.

    Args:
        grid: Grid array of shape [T, H, W, C].
        pgids: Cell ID array of shape [H, W].
        time_steps: Time array of shape [T] (datetime64[M]).
        feature_names: List of C feature column names.
        land_pgids: Optional set of land cell IDs for filtering.
        month_id_epoch: Base year for month_id encoding.
        metadata: Optional dict of provenance info.

    Returns:
        FeatureFrame with dense land-cell time series.
    """
    flat_data, all_month_ids, all_pgids = _flatten_grid(
        grid, pgids, time_steps, month_id_epoch, land_pgids
    )

    return FeatureFrame(
        y_features=flat_data,
        identifiers={
            "time": all_month_ids,
            "unit": all_pgids.astype(np.int32),
        },
        feature_names=list(feature_names),
        metadata=metadata,
    )
