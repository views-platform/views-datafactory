"""Temporal query parsing — flexible input to datetime64[M] range.

Accepts ISO strings, VIEWS month_ids, year-only strings, or None.
Delegates to datafactory_priogrid for the VIEWS epoch convention.
"""

from __future__ import annotations

import re

import numpy as np

from datafactory_priogrid.temporal_generator import from_views_month_id

__all__ = ["parse_time_range", "time_range_to_slice"]

_YEAR_RE = re.compile(r"^\d{4}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_single(value: str | int) -> np.datetime64:
    """Parse a single time value to datetime64[M]."""
    if isinstance(value, int):
        # VIEWS month_id
        return from_views_month_id(value).item()

    if _YEAR_RE.match(value):
        return np.datetime64(f"{value}-01", "M")

    if _MONTH_RE.match(value):
        return np.datetime64(value, "M")

    if _DATE_RE.match(value):
        # Truncate to month
        return np.datetime64(value[:7], "M")

    msg = (
        f"Cannot parse time value {value!r}. "
        f"Expected: 'YYYY', 'YYYY-MM', 'YYYY-MM-DD', "
        f"or int (VIEWS month_id)."
    )
    raise ValueError(msg)


def parse_time_range(
    start: str | int | None = None,
    end: str | int | None = None,
    *,
    time_steps: np.ndarray | None = None,
) -> tuple[np.datetime64, np.datetime64]:
    """Parse flexible time inputs to a datetime64[M] range.

    Args:
        start: Start of range (inclusive). Accepts ISO string,
            VIEWS month_id (int), year-only string, or None
            (uses first time step).
        end: End of range (inclusive). Same formats as start,
            or None (uses last time step). Year-only strings
            resolve to December of that year.
        time_steps: Reference array for None defaults. Required
            if start or end is None.

    Returns:
        (start_dt, end_dt) as datetime64[M], both inclusive.

    Raises:
        ValueError: If input cannot be parsed or time_steps is
            needed but not provided.
    """
    if start is None:
        if time_steps is None:
            msg = "start=None requires time_steps"
            raise ValueError(msg)
        start_dt = time_steps[0]
    else:
        start_dt = _parse_single(start)

    if end is None:
        if time_steps is None:
            msg = "end=None requires time_steps"
            raise ValueError(msg)
        end_dt = time_steps[-1]
    elif isinstance(end, str) and _YEAR_RE.match(end):
        # Year-only end → December of that year
        end_dt = np.datetime64(f"{end}-12", "M")
    else:
        end_dt = _parse_single(end)

    return np.datetime64(start_dt, "M"), np.datetime64(end_dt, "M")


def time_range_to_slice(
    time_steps: np.ndarray,
    start: np.datetime64,
    end: np.datetime64,
) -> slice:
    """Convert a datetime64 range to an index slice into time_steps.

    Both start and end are inclusive. Returns a slice object
    suitable for indexing the T dimension of the grid.

    Raises:
        ValueError: If the range has no overlap with time_steps.
    """
    mask = (time_steps >= start) & (time_steps <= end)
    indices = np.where(mask)[0]
    if len(indices) == 0:
        msg = (
            f"Time range {start}..{end} has no overlap with "
            f"time_steps ({time_steps[0]}..{time_steps[-1]})"
        )
        raise ValueError(msg)
    return slice(int(indices[0]), int(indices[-1]) + 1)
