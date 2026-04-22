"""Grid array to country-month DataFrame conversion.

Aggregates the canonical [T, H, W, C] grid to country-month level:
sums feature values per (month_id, country_id) using a country
identifier feature (default: gaul0_code) as the grouping key.

Reuses _flatten_grid() from grid_to_dataframe for the initial
flattening step.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from datafactory_adapters.grid_to_dataframe import _flatten_grid

logger = logging.getLogger(__name__)

__all__ = ["grid_to_country_month"]


def grid_to_country_month(
    grid: np.ndarray,
    pgids: np.ndarray,
    time_steps: np.ndarray,
    feature_names: list[str],
    *,
    country_feature: str = "gaul0_code",
    land_pgids: set[int] | None = None,
    month_id_epoch: int = 0,
) -> pd.DataFrame:
    """Convert a [T, H, W, C] grid to a country-month DataFrame.

    Flattens the grid to cell level, then groups by
    (month_id, country_id) and sums numeric features.

    Args:
        grid: Grid array of shape [T, H, W, C].
        pgids: Cell ID array of shape [H, W].
        time_steps: Time array of shape [T] (datetime64[M]).
        feature_names: List of C feature column names.
        country_feature: Name of the feature used as country
            identifier for grouping (default: "gaul0_code").
        land_pgids: Optional set of land cell IDs. If provided,
            only land cells are included.
        month_id_epoch: Base year for month_id encoding.

    Returns:
        DataFrame with (month_id, country_id) MultiIndex and
        one column per feature (excluding the country_feature).

    Raises:
        ValueError: If country_feature is not in feature_names.
    """
    if country_feature not in feature_names:
        msg = (
            f"Country feature {country_feature!r} not in "
            f"feature_names: {feature_names}"
        )
        raise ValueError(msg)

    flat_data, all_month_ids, all_pgids = _flatten_grid(
        grid, pgids, time_steps, month_id_epoch, land_pgids,
    )

    country_idx = feature_names.index(country_feature)
    country_ids = flat_data[:, country_idx].astype(np.int64)

    # Exclude ocean cells (country_id <= 0)
    land_mask = country_ids > 0
    flat_data = flat_data[land_mask]
    all_month_ids = all_month_ids[land_mask]
    country_ids = country_ids[land_mask]

    # Drop the country feature column from the data
    value_features = [
        f for i, f in enumerate(feature_names) if i != country_idx
    ]
    value_data = np.delete(flat_data, country_idx, axis=1)

    df = pd.DataFrame(
        value_data,
        columns=value_features,
    )
    df["month_id"] = all_month_ids
    df["country_id"] = country_ids

    result = (
        df.groupby(["month_id", "country_id"], sort=True)
        .sum()
    )

    return result
