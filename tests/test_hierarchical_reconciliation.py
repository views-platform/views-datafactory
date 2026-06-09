"""Tests for ADR-040 hierarchical reconciliation invariants.

Invariant 2: within the GAUL reconciliation family, summing count
features grouped by gaul0, gaul1, or gaul2 must produce identical
totals. Every L2 unit nests within exactly one L1, every L1 within
exactly one L0.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Green tier — correctness
# ---------------------------------------------------------------------------


class TestGreenHierarchyNesting:
    """Synthetic data: structural nesting invariant."""

    def test_consistent_hierarchy_passes(self) -> None:
        from datafactory_adapters._reconciliation import (
            assert_hierarchical_reconciliation,
        )

        # 6 cells: 2 countries, each with 2 provinces, each with 1 district
        gaul0 = np.array([1, 1, 1, 2, 2, 2])
        gaul1 = np.array([10, 10, 11, 20, 20, 21])
        gaul2 = np.array([100, 101, 110, 200, 201, 210])
        events = np.array([5.0, 3.0, 2.0, 1.0, 4.0, 0.0])

        assert_hierarchical_reconciliation(
            gaul0=gaul0, gaul1=gaul1, gaul2=gaul2,
            feature_values=events,
        )

    def test_broken_nesting_detected(self) -> None:
        from datafactory_adapters._reconciliation import (
            assert_hierarchical_reconciliation,
        )

        # L2=100 maps to both L1=10 and L1=20 — violation
        gaul0 = np.array([1, 2])
        gaul1 = np.array([10, 20])
        gaul2 = np.array([100, 100])
        events = np.array([5.0, 3.0])

        with pytest.raises(RuntimeError, match="nesting violation"):
            assert_hierarchical_reconciliation(
                gaul0=gaul0, gaul1=gaul1, gaul2=gaul2,
                feature_values=events,
            )


# ---------------------------------------------------------------------------
# Beige tier — edge cases
# ---------------------------------------------------------------------------


class TestBeigeHierarchy:
    """Edge cases for hierarchy reconciliation."""

    def test_single_level_trivially_passes(self) -> None:
        from datafactory_adapters._reconciliation import (
            assert_hierarchical_reconciliation,
        )

        gaul0 = np.array([1, 1, 2, 2])
        events = np.array([5.0, 3.0, 1.0, 4.0])

        # Only gaul0, no hierarchy to reconcile
        assert_hierarchical_reconciliation(
            gaul0=gaul0, gaul1=None, gaul2=None,
            feature_values=events,
        )

    def test_all_zero_events_passes(self) -> None:
        from datafactory_adapters._reconciliation import (
            assert_hierarchical_reconciliation,
        )

        gaul0 = np.array([1, 1, 2, 2])
        gaul1 = np.array([10, 10, 20, 20])
        gaul2 = np.array([100, 101, 200, 201])
        events = np.zeros(4)

        assert_hierarchical_reconciliation(
            gaul0=gaul0, gaul1=gaul1, gaul2=gaul2,
            feature_values=events,
        )


# ---------------------------------------------------------------------------
# Red tier — failure modes
# ---------------------------------------------------------------------------


class TestRedHierarchy:
    """Failure modes for hierarchy reconciliation."""

    def test_cross_level_nesting_violation_raises(self) -> None:
        from datafactory_adapters._reconciliation import (
            assert_hierarchical_reconciliation,
        )

        # L1=20 appears under both L0=1 and L0=2 — nesting violation
        gaul0 = np.array([1, 1, 2, 2])
        gaul1 = np.array([10, 20, 20, 21])  # L1=20 maps to L0=1 AND L0=2
        gaul2 = np.array([100, 200, 201, 210])
        events = np.array([5.0, 3.0, 1.0, 4.0])

        with pytest.raises(RuntimeError, match="nesting violation"):
            assert_hierarchical_reconciliation(
                gaul0=gaul0, gaul1=gaul1, gaul2=gaul2,
                feature_values=events,
            )


# ---------------------------------------------------------------------------
# Real-data test — skips in CI
# ---------------------------------------------------------------------------


_DATA_DIR = Path("data/raw/gaul_admin")


class TestRealDataHierarchy:
    """Verify real GAUL Parquet files have consistent nesting."""

    @pytest.mark.skipif(
        not (_DATA_DIR / "gaul0_code.parquet").exists(),
        reason="No local GAUL data — run generate_area_majority_gaul.py first",
    )
    def test_real_gaul_hierarchy_nesting(self) -> None:
        import pyarrow.parquet as pq

        from datafactory_adapters._reconciliation import (
            check_nesting,
        )

        g0 = pq.read_table(_DATA_DIR / "gaul0_code.parquet")
        g1 = pq.read_table(_DATA_DIR / "gaul1_code.parquet")
        g2 = pq.read_table(_DATA_DIR / "gaul2_code.parquet")

        # Build gid→code mappings
        g0_map = dict(zip(
            g0.column("gid").to_pylist(),
            g0.column("value").to_pylist(),
            strict=True,
        ))
        g1_map = dict(zip(
            g1.column("gid").to_pylist(),
            g1.column("value").to_pylist(),
            strict=True,
        ))
        g2_map = dict(zip(
            g2.column("gid").to_pylist(),
            g2.column("value").to_pylist(),
            strict=True,
        ))

        # Only check cells present in all three levels
        common_gids = sorted(
            set(g0_map) & set(g1_map) & set(g2_map)
        )
        assert len(common_gids) > 0

        gaul0 = np.array([g0_map[g] for g in common_gids])
        gaul1 = np.array([g1_map[g] for g in common_gids])
        gaul2 = np.array([g2_map[g] for g in common_gids])

        violations = check_nesting(gaul0=gaul0, gaul1=gaul1, gaul2=gaul2)
        assert len(violations) == 0, (
            f"GAUL hierarchy has {len(violations)} nesting violations: "
            f"{violations[:5]}"
        )
