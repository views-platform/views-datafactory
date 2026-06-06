"""ADR-040 hierarchical reconciliation for the GAUL admin family.

Invariant 2: every L2 unit nests within exactly one L1, every L1
within exactly one L0. Summing extensive features by any level
produces identical totals.

Uses if/raise RuntimeError — assert is stripped with -O.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "assert_hierarchical_reconciliation",
    "check_nesting",
]


def check_nesting(
    gaul0: np.ndarray,
    gaul1: np.ndarray | None = None,
    gaul2: np.ndarray | None = None,
) -> list[str]:
    """Return list of nesting violation descriptions (empty = clean)."""
    violations: list[str] = []

    if gaul1 is not None:
        l1_to_l0: dict[int, int] = {}
        for g1, g0 in zip(gaul1, gaul0, strict=True):
            if g1 in l1_to_l0:
                if l1_to_l0[g1] != g0:
                    violations.append(
                        f"L1={g1} maps to both L0={l1_to_l0[g1]} and L0={g0}"
                    )
            else:
                l1_to_l0[g1] = g0

    if gaul1 is not None and gaul2 is not None:
        l2_to_l1: dict[int, int] = {}
        for g2, g1 in zip(gaul2, gaul1, strict=True):
            if g2 in l2_to_l1:
                if l2_to_l1[g2] != g1:
                    violations.append(
                        f"L2={g2} maps to both L1={l2_to_l1[g2]} and L1={g1}"
                    )
            else:
                l2_to_l1[g2] = g1

    return violations


def assert_hierarchical_reconciliation(
    gaul0: np.ndarray,
    gaul1: np.ndarray | None = None,
    gaul2: np.ndarray | None = None,
    feature_values: np.ndarray | None = None,
) -> None:
    """Verify GAUL hierarchy nesting and (optionally) sum reconciliation."""
    violations = check_nesting(gaul0=gaul0, gaul1=gaul1, gaul2=gaul2)
    if violations:
        raise RuntimeError(
            f"Hierarchical nesting violation (ADR-040): "
            f"{len(violations)} violation(s): {'; '.join(violations[:5])}"
        )

    if feature_values is None:
        return

    # Sum reconciliation: totals grouped by each level must match
    levels = {"gaul0": gaul0}
    if gaul1 is not None:
        levels["gaul1"] = gaul1
    if gaul2 is not None:
        levels["gaul2"] = gaul2

    totals: dict[str, float] = {}
    for name, codes in levels.items():
        level_total = sum(
            float(feature_values[codes == c].sum())
            for c in np.unique(codes)
        )
        totals[name] = level_total

    level_names = list(totals.keys())
    for i in range(1, len(level_names)):
        a, b = level_names[0], level_names[i]
        if not np.allclose(totals[a], totals[b], rtol=1e-6, atol=1e-4):
            raise RuntimeError(
                f"Hierarchical sum mismatch (ADR-040): "
                f"{a}={totals[a]:.6f} != {b}={totals[b]:.6f}"
            )
