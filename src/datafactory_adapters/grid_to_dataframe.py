"""Grid array to DataFrame conversion.

Converts the canonical [T, H, W, C] grid output to a pandas
DataFrame with (month_id, priogrid_id) MultiIndex. Supports
land filtering and configurable month_id encoding.

pandas is an OPTIONAL extra (``views-datafactory[pandas]``) and is
imported inside the function that builds the frame, so importing
this module — or anything else in the package — stays pandas-free.

One concept per module (#379): the shared flattening primitive lives
in ``_flatten.py`` and the frame-native converter in
``grid_to_feature_frame.py``, so deleting the pandas tier one day is
a file deletion rather than surgery.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # annotations only — never imported at runtime
    import pandas as pd

from datafactory_adapters._flatten import _flatten_grid

logger = logging.getLogger(__name__)

__all__ = ["grid_to_dataframe"]


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
        DataFrame with (month_id, priogrid_id) MultiIndex
        and one column per feature.
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - env-dependent
        msg = (
            "DataFrame output requires pandas, which is an optional "
            "extra of views-datafactory. Install it with: "
            'pip install "views-datafactory[pandas]"'
        )
        raise ImportError(msg) from exc

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
        names=["month_id", "priogrid_id"],
    )
    df = pd.DataFrame(
        flat_data, index=index, columns=feature_names
    )
    return df.sort_index()
