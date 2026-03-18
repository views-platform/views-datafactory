"""Temporal index generator -- pure numpy, same style as generator.py.

Generates a 1-D array of numpy datetime64[M] values representing
monthly time steps. Also provides adapter functions for the VIEWS
platform month_id convention.
"""

import logging

import numpy as np

from datafactory_priogrid.temporal_config import TemporalConfig

logger = logging.getLogger(__name__)

# VIEWS epoch: month_id 1 = January 1980
_VIEWS_EPOCH = np.datetime64("1980-01", "M")

DEFAULT_TEMPORAL_CONFIG = TemporalConfig()


def generate_time_steps(
    config: TemporalConfig = DEFAULT_TEMPORAL_CONFIG,
) -> np.ndarray:
    """Generate monthly time step array for the configured range.

    Returns:
        1-D array of datetime64[M] values, length config.n_steps.
    """

    start = config.start_dt
    # np.arange end is exclusive, so add 1 month
    end = config.end_dt + np.timedelta64(1, "M")
    steps = np.arange(start, end, dtype="datetime64[M]")

    logger.info(
        "Generated %d time steps (%s to %s)",
        len(steps),
        config.start_dt,
        config.end_dt,
    )
    return steps


def to_views_month_id(dt: np.datetime64 | np.ndarray) -> np.ndarray:
    """Convert datetime64[M] to VIEWS month_id (int32).

    VIEWS convention: month_id = (year - 1980) * 12 + month.
    January 1980 = 1.

    Note: Returns 0 for December 1979 and negative values for earlier
    dates. If the VIEWS convention requires month_id >= 1, callers
    should validate the result.
    """
    dt = np.asarray(dt, dtype="datetime64[M]")
    # Months since epoch (0-based), then +1 for 1-based VIEWS convention
    offset = (dt - _VIEWS_EPOCH).astype(np.int32) + 1
    return offset


def from_views_month_id(month_id: int | np.ndarray) -> np.ndarray:
    """Convert VIEWS month_id (int) to datetime64[M].

    Inverse of to_views_month_id.
    """
    month_id = np.asarray(month_id, dtype=np.int32)
    return _VIEWS_EPOCH + (month_id - 1).astype("timedelta64[M]")
