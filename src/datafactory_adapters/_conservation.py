"""ADR-040 count conservation for the CM aggregation layer.

Invariant 1 at CM boundary: for extensive features (count/sum),
grid_total = land_total + excluded_total.

Uses np.allclose for float32 sums (rounding tolerance).
Uses if/raise RuntimeError — assert is stripped with -O.
"""

from __future__ import annotations

import numpy as np

__all__ = ["assert_cm_conservation"]

_EXTENSIVE_PREFIXES = ("ged_", "acled_")


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
