"""Tests for ADR-040 count conservation invariants.

Invariant 1: placed + excluded = input at every pipeline layer boundary.

Compilation layer: placed + skipped_spatial + skipped_temporal = input_rows
CM aggregation: sum(country totals) + sum(excluded) = sum(all cells)

Uses if/raise RuntimeError, not assert — assert is stripped with -O.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Green tier — correctness
# ---------------------------------------------------------------------------


class TestGreenPlacementConservation:
    """Compilation-layer conservation: placed + skipped = input."""

    def test_exact_conservation_passes(self) -> None:
        from datafactory_compilation.conservation import (
            PlacementAccounting,
            assert_placement_conservation,
        )

        acc = PlacementAccounting(
            n_input=100,
            n_placed=80,
            n_skipped_spatial=15,
            n_skipped_temporal=5,
        )
        assert_placement_conservation(acc)

    def test_spatial_skip_conservation_passes(self) -> None:
        from datafactory_compilation.conservation import (
            PlacementAccounting,
            assert_placement_conservation,
        )

        acc = PlacementAccounting(
            n_input=50,
            n_placed=30,
            n_skipped_spatial=20,
            n_skipped_temporal=0,
        )
        assert_placement_conservation(acc)

    def test_violation_raises_runtime_error(self) -> None:
        from datafactory_compilation.conservation import (
            PlacementAccounting,
            assert_placement_conservation,
        )

        acc = PlacementAccounting(
            n_input=100,
            n_placed=80,
            n_skipped_spatial=15,
            n_skipped_temporal=3,  # 80+15+3=98 != 100
        )
        with pytest.raises(RuntimeError, match="Count conservation violated"):
            assert_placement_conservation(acc)


class TestGreenCMConservation:
    """CM aggregation layer: grid_total = land_total + excluded_total."""

    def test_cm_conservation_exact_match(self) -> None:
        from datafactory_adapters._conservation import assert_cm_conservation

        feature_names = ["ged_sb_best", "ged_ns_best", "gaul0_code"]
        n_cells = 20
        flat_all = np.ones((n_cells, 3), dtype=np.float32)
        flat_all[:, 2] = np.repeat([10, 20], 10)

        land_mask = flat_all[:, 2] > 0
        excluded_mask = ~land_mask

        flat_land = flat_all[land_mask]
        excluded_data = flat_all[excluded_mask]

        assert_cm_conservation(
            feature_names, flat_all, flat_land, excluded_data,
        )

    def test_cm_conservation_float_tolerance(self) -> None:
        from datafactory_adapters._conservation import assert_cm_conservation

        feature_names = ["ged_sb_best", "gaul0_code"]
        n_cells = 10000
        rng = np.random.default_rng(42)
        flat_all = rng.random((n_cells, 2)).astype(np.float32)
        flat_all[:, 1] = 10

        land_mask = np.ones(n_cells, dtype=bool)
        land_mask[:100] = False
        excluded_mask = ~land_mask

        flat_land = flat_all[land_mask]
        excluded_data = flat_all[excluded_mask]

        assert_cm_conservation(
            feature_names, flat_all, flat_land, excluded_data,
        )


# ---------------------------------------------------------------------------
# Beige tier — edge cases
# ---------------------------------------------------------------------------


class TestBeigePlacementConservation:
    """Edge cases for compilation conservation."""

    def test_zero_events_conservation(self) -> None:
        from datafactory_compilation.conservation import (
            PlacementAccounting,
            assert_placement_conservation,
        )

        acc = PlacementAccounting(
            n_input=0, n_placed=0,
            n_skipped_spatial=0, n_skipped_temporal=0,
        )
        assert_placement_conservation(acc)


class TestBeigeCMConservation:
    """Edge cases for CM conservation."""

    def test_all_excluded_conservation(self) -> None:
        from datafactory_adapters._conservation import assert_cm_conservation

        feature_names = ["ged_sb_best", "gaul0_code"]
        flat_all = np.ones((10, 2), dtype=np.float32)
        flat_all[:, 1] = 0  # all ocean

        land_mask = flat_all[:, 1] > 0
        excluded_mask = ~land_mask
        flat_land = flat_all[land_mask]
        excluded_data = flat_all[excluded_mask]

        assert_cm_conservation(
            feature_names, flat_all, flat_land, excluded_data,
        )

    def test_no_extensive_features_skips_check(self) -> None:
        from datafactory_adapters._conservation import assert_cm_conservation

        feature_names = ["hdi", "democracy_score", "gaul0_code"]
        flat_all = np.ones((10, 3), dtype=np.float32)

        # Even with mismatched shapes, should not raise
        # because no features match extensive prefixes
        flat_land = flat_all[:5]
        excluded_data = flat_all[5:]

        assert_cm_conservation(
            feature_names, flat_all, flat_land, excluded_data,
        )


# ---------------------------------------------------------------------------
# Red tier — failure modes
# ---------------------------------------------------------------------------


class TestRedCMConservation:
    """Failure modes for CM conservation."""

    def test_cm_violation_raises_runtime_error(self) -> None:
        from datafactory_adapters._conservation import assert_cm_conservation

        feature_names = ["ged_sb_best", "gaul0_code"]
        flat_all = np.ones((10, 2), dtype=np.float32)
        flat_all[:, 1] = 10

        # Tamper: land gets all rows, but excluded also claims some
        flat_land = flat_all.copy()
        excluded_data = np.ones((3, 2), dtype=np.float32)

        with pytest.raises(RuntimeError, match="conservation violated"):
            assert_cm_conservation(
                feature_names, flat_all, flat_land, excluded_data,
            )

    def test_uses_raise_not_assert(self) -> None:
        """Conservation must use if/raise, not assert (stripped with -O)."""
        from datafactory_compilation import conservation

        source = inspect.getsource(conservation.assert_placement_conservation)
        assert "raise RuntimeError" in source
        assert "assert " not in source.replace(
            "assert_placement_conservation", ""
        )
