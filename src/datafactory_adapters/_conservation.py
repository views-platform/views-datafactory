"""ADR-040 count conservation for the CM aggregation layer.

Invariant 1 at CM boundary: for extensive features (count/sum),
grid_total = land_total + excluded_total.

Uses np.allclose for float32 sums (rounding tolerance).
Uses if/raise RuntimeError — assert is stripped with -O.
"""

from __future__ import annotations

import numpy as np

__all__ = ["assert_cm_conservation", "assert_no_unexpected_nan"]

# Extend when new count/sum sources are added (e.g. WDI).
_EXTENSIVE_PREFIXES = ("ged_", "acled_")


def assert_no_unexpected_nan(
    feature_names: list[str],
    data: np.ndarray,
    extensive_prefixes: tuple[str, ...] = _EXTENSIVE_PREFIXES,
    label: str = "grid",
) -> None:
    """Raise if any extensive feature column contains NaN.

    Extensive features (counts) should never be NaN in the assembled
    grid.  NaN in these columns indicates a bug, not missing data.
    nansum would silently exclude these values, weakening the
    conservation invariant (C-291).
    """
    indices = [
        i for i, f in enumerate(feature_names)
        if f.startswith(extensive_prefixes)
    ]
    if not indices or data.size == 0:
        return

    for i in indices:
        n_nan = int(np.isnan(data[:, i]).sum())
        if n_nan > 0:
            raise RuntimeError(
                f"Unexpected NaN in extensive feature "
                f"{feature_names[i]!r} ({label}): {n_nan} NaN values. "
                f"Extensive features must not contain NaN — "
                f"this indicates a data pipeline bug, not missing data."
            )


def assert_cm_conservation(
    feature_names: list[str],
    flat_data_all: np.ndarray,
    flat_data_land: np.ndarray,
    excluded_data: np.ndarray,
    extensive_prefixes: tuple[str, ...] = _EXTENSIVE_PREFIXES,
) -> None:
    """Verify grid_total = land_total + excluded_total for extensive features."""
    indices = [
        i for i, f in enumerate(feature_names)
        if f.startswith(extensive_prefixes)
    ]
    if not indices:
        return

    assert_no_unexpected_nan(
        feature_names, flat_data_all, extensive_prefixes, "all",
    )
    assert_no_unexpected_nan(
        feature_names, flat_data_land, extensive_prefixes, "land",
    )
    assert_no_unexpected_nan(
        feature_names, excluded_data, extensive_prefixes, "excluded",
    )

    for i in indices:
        grid_total = float(np.nansum(flat_data_all[:, i], dtype=np.float64))
        land_total = float(np.nansum(flat_data_land[:, i], dtype=np.float64))
        excl_total = float(np.nansum(excluded_data[:, i], dtype=np.float64))
        recon = land_total + excl_total

        if not np.allclose(grid_total, recon, rtol=1e-6, atol=1e-4):
            raise RuntimeError(
                f"CM conservation violated (ADR-040) for "
                f"{feature_names[i]!r}: grid_total={grid_total:.6f} != "
                f"land_total={land_total:.6f} + "
                f"excluded_total={excl_total:.6f} = {recon:.6f}"
            )
