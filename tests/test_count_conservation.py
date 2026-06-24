"""Tests for ADR-040 count conservation invariants.

Invariant 1: placed + excluded = input at every pipeline layer boundary.

Compilation layer: placed + skipped_spatial + skipped_temporal = input_rows
CM aggregation: sum(country totals) + sum(excluded) = sum(all cells)

Uses if/raise RuntimeError, not assert — assert is stripped with -O.
"""

from __future__ import annotations

import inspect
import warnings

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

    def test_nan_in_extensive_feature_raises(self) -> None:
        """C-291: NaN in extensive feature must raise before nansum."""
        from datafactory_adapters._conservation import assert_cm_conservation

        feature_names = ["ged_sb_best", "gaul0_code"]
        flat_all = np.ones((10, 2), dtype=np.float32)
        flat_all[:, 1] = 10
        flat_all[3, 0] = np.nan  # inject NaN into extensive feature

        land_mask = np.ones(10, dtype=bool)
        land_mask[:2] = False

        with pytest.raises(RuntimeError, match="Unexpected NaN"):
            assert_cm_conservation(
                feature_names,
                flat_all,
                flat_all[land_mask],
                flat_all[~land_mask],
            )

    def test_nan_in_non_extensive_feature_does_not_raise(self) -> None:
        """NaN in intensive features should not trigger the guard."""
        from datafactory_adapters._conservation import assert_cm_conservation

        feature_names = ["ged_sb_best", "shdi"]
        flat_all = np.ones((10, 2), dtype=np.float32)
        flat_all[3, 1] = np.nan  # NaN in intensive feature only

        land_mask = np.ones(10, dtype=bool)
        land_mask[:2] = False

        assert_cm_conservation(
            feature_names,
            flat_all,
            flat_all[land_mask],
            flat_all[~land_mask],
        )


class TestRedNaNGuard:
    """Direct tests for assert_no_unexpected_nan (C-291)."""

    def test_nan_detected_in_all_partition(self) -> None:
        from datafactory_adapters._conservation import (
            assert_no_unexpected_nan,
        )

        feature_names = ["ged_sb_best", "gaul0_code"]
        data = np.ones((5, 2), dtype=np.float32)
        data[2, 0] = np.nan

        with pytest.raises(RuntimeError, match="Unexpected NaN"):
            assert_no_unexpected_nan(feature_names, data)

    def test_clean_data_passes(self) -> None:
        from datafactory_adapters._conservation import (
            assert_no_unexpected_nan,
        )

        feature_names = ["ged_sb_best", "acled_count"]
        data = np.ones((100, 2), dtype=np.float32)
        assert_no_unexpected_nan(feature_names, data)

    def test_empty_array_passes(self) -> None:
        from datafactory_adapters._conservation import (
            assert_no_unexpected_nan,
        )

        feature_names = ["ged_sb_best"]
        data = np.ones((0, 1), dtype=np.float32)
        assert_no_unexpected_nan(feature_names, data)


# ---------------------------------------------------------------------------
# Green tier — intensive feature warning (C-241)
# ---------------------------------------------------------------------------


class TestGreenIntensiveWarning:
    """C-241: Warning when intensive features included in CM aggregation."""

    def _make_grid(
        self, feature_names: list[str], n_t: int = 2,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n_h, n_w = 3, 4
        n_c = len(feature_names)
        grid = np.ones((n_t, n_h, n_w, n_c), dtype=np.float32)
        ci = feature_names.index("gaul0_code")
        grid[:, :, :, ci] = 10
        pgids = np.arange(1, n_h * n_w + 1).reshape(n_h, n_w)
        time_steps = np.array(
            ["2020-01", "2020-02"], dtype="datetime64[M]",
        )[:n_t]
        return grid, pgids, time_steps

    def test_intensive_feature_warning_emitted(self) -> None:
        from datafactory_adapters.grid_to_country_month import (
            grid_to_country_month,
        )

        features = ["ged_sb_best", "shdi", "gaul0_code"]
        grid, pgids, ts = self._make_grid(features)

        with pytest.warns(UserWarning, match="Intensive features"):
            grid_to_country_month(
                grid, pgids, ts, features,
            )

    def test_no_warning_for_extensive_only(self) -> None:
        from datafactory_adapters.grid_to_country_month import (
            grid_to_country_month,
        )

        features = ["ged_sb_best", "acled_count", "gaul0_code"]
        grid, pgids, ts = self._make_grid(features)

        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            grid_to_country_month(
                grid, pgids, ts, features,
            )


class TestRedFloat64Regression:
    """C-249: Prove dtype=np.float64 in nansum provides precision."""

    def test_float32_has_nonzero_partition_error(self) -> None:
        """Float32 accumulation introduces measurable partition error.

        At 500K cells with values in [10, 100], float32 nansum
        produces a nonzero gap between sum(all) and sum(land)+sum(excl),
        while float64 produces zero gap.  The production code uses
        float64 (dtype=np.float64 in _conservation.py) to guarantee
        exact partition-sum equality.
        """
        n_cells = 500_000
        rng = np.random.default_rng(99)
        flat_all = (rng.random((n_cells, 2)) * 90 + 10).astype(np.float32)
        flat_all[:, 1] = 10

        land_mask = np.ones(n_cells, dtype=bool)
        land_mask[:5000] = False

        flat_land = flat_all[land_mask]
        flat_excl = flat_all[~land_mask]

        f32_grid = float(np.nansum(flat_all[:, 0]))
        f32_land = float(np.nansum(flat_land[:, 0]))
        f32_excl = float(np.nansum(flat_excl[:, 0]))
        f32_gap = abs(f32_grid - (f32_land + f32_excl))

        f64_grid = float(np.nansum(flat_all[:, 0], dtype=np.float64))
        f64_land = float(np.nansum(flat_land[:, 0], dtype=np.float64))
        f64_excl = float(np.nansum(flat_excl[:, 0], dtype=np.float64))
        f64_gap = abs(f64_grid - (f64_land + f64_excl))

        assert f32_gap > 0.01, (
            f"Expected measurable float32 gap but got {f32_gap:.10f}"
        )
        assert f64_gap < 1e-10, (
            f"Float64 should have near-zero gap but got {f64_gap:.10f}"
        )

    def test_production_code_passes_at_scale(self) -> None:
        """Conservation check passes at production scale with float64."""
        from datafactory_adapters._conservation import assert_cm_conservation

        feature_names = ["ged_sb_best", "gaul0_code"]
        n_cells = 500_000
        rng = np.random.default_rng(99)
        flat_all = (rng.random((n_cells, 2)) * 90 + 10).astype(np.float32)
        flat_all[:, 1] = 10

        land_mask = np.ones(n_cells, dtype=bool)
        land_mask[:5000] = False

        assert_cm_conservation(
            feature_names, flat_all,
            flat_all[land_mask], flat_all[~land_mask],
        )
