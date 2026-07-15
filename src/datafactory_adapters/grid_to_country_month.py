"""Grid array to country-month DataFrame conversion.

Aggregates the canonical [T, H, W, C] grid to country-month level:
sums feature values per (month_id, country_id) using a country
identifier feature (default: gaul0_code) as the grouping key.

Reuses _flatten_grid() from grid_to_dataframe for the initial
flattening step.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd

from datafactory_adapters._conservation import assert_cm_conservation
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
    feature_agg_types: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Convert a [T, H, W, C] grid to a country-month DataFrame.

    Flattens the grid to cell level, then groups by
    (month_id, country_id) and sums numeric features.

    When *feature_agg_types* is provided (ADR-048), intensive
    features raise ``ValueError`` (fail-loud, ADR-011) and static
    features are excluded from the aggregation.

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
        feature_agg_types: Feature name → aggregation type mapping
            from the source registry (ADR-048). When provided,
            enables type-aware aggregation.

    Returns:
        DataFrame with (month_id, country_id) MultiIndex and
        one column per extensive feature.

    Raises:
        ValueError: If country_feature is not in feature_names,
            or if intensive features are present when
            feature_agg_types is provided.
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
    excluded_mask = ~land_mask
    n_excluded = int(excluded_mask.sum())

    if n_excluded > 0:
        # Declared extensive features only (ADR-003/ADR-048, C-302):
        # no name inference. Without the declaration the warning is
        # skipped — the conservation check below is likewise a no-op
        # for such callers (C-301).
        event_indices = (
            [
                i for i, f in enumerate(feature_names)
                if feature_agg_types.get(f) == "extensive"
            ]
            if feature_agg_types is not None
            else []
        )
        if event_indices:
            excluded_events = flat_data[excluded_mask][:, event_indices]
            rows_with_events = np.nansum(excluded_events, axis=1) > 0
            n_with_events = int(rows_with_events.sum())
            if n_with_events > 0:
                warnings.warn(
                    f"CM aggregation excluded {n_excluded} cell-months "
                    f"with country_id <= 0 (unmapped GAUL centroids). "
                    f"{n_with_events} have nonzero event values. "
                    f"See C-149 in the technical risk register.",
                    UserWarning,
                    stacklevel=2,
                )

    # ADR-040 Invariant 1: grid_total = land_total + excluded_total
    assert_cm_conservation(
        feature_names,
        flat_data,
        flat_data[land_mask],
        flat_data[excluded_mask],
        feature_agg_types=feature_agg_types,
    )

    flat_data = flat_data[land_mask]
    all_month_ids = all_month_ids[land_mask]
    country_ids = country_ids[land_mask]

    # Drop the country feature column from the data
    value_features = [
        f for i, f in enumerate(feature_names) if i != country_idx
    ]
    value_data = np.delete(flat_data, country_idx, axis=1)

    if feature_agg_types is not None:
        intensive = [
            f for f in value_features
            if feature_agg_types.get(f) == "intensive"
        ]
        if intensive:
            msg = (
                f"Country-month aggregation cannot sum intensive "
                f"features (ADR-048, ADR-011). Intensive features "
                f"are indices, not counts — their sums across "
                f"cells are not meaningful. Remove these features "
                f"or use output_format='dataframe': {intensive}"
            )
            raise ValueError(msg)
        # Exclude static features from aggregation
        keep = [
            i for i, f in enumerate(value_features)
            if feature_agg_types.get(f) != "static"
        ]
        value_features = [value_features[i] for i in keep]
        value_data = value_data[:, keep]

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
