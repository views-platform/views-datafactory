"""Shared validation helpers for adapter modules."""

from __future__ import annotations

import numpy as np


def validate_grid_pgids(
    grid: np.ndarray, pgids: np.ndarray
) -> None:
    """Validate grid [T, H, W, C] and pgids [H, W] compatibility.

    Raises:
        ValueError: If grid is not 4D, pgids is not 2D, or
            spatial dimensions don't match.
    """
    if grid.ndim != 4:
        msg = f"grid must be 4D [T, H, W, C], got {grid.ndim}D"
        raise ValueError(msg)
    validate_pgids(pgids)
    if grid.shape[1:3] != pgids.shape:
        msg = (
            f"grid spatial dims {grid.shape[1:3]} "
            f"!= pgids shape {pgids.shape}"
        )
        raise ValueError(msg)


def validate_pgids(pgids: np.ndarray) -> None:
    """Validate pgids is 2D [H, W].

    Raises:
        ValueError: If pgids is not 2D.
    """
    if pgids.ndim != 2:
        msg = f"pgids must be 2D [H, W], got {pgids.ndim}D"
        raise ValueError(msg)
