"""Falsification stubs: ADR-003 compliance epic #290 completeness.

Source: /falsify 2026-06-28
Claim: Epic #290 is complete and there is nothing left to do.
Verdict: FALSIFIED (1 hard, 2 soft) → addressed 2026-06-28.

P2 (hard): ADR-048 §5 said _SOURCE_DISPLAY_NAMES is deleted,
    but it still exists. Fixed: ADR corrected to say it is retained
    (display purpose, not inference). C-299 registered (Tier 4).
P4 (soft): Zarr path returns source_features={}, silently
    disabling pre-coverage warnings for zarr consumers.
    C-300 registered (Tier 4, deferred).
P6 (soft): assert_cm_conservation is a complete no-op when
    feature_agg_types=None — direct callers lose conservation.
    C-301 registered (Tier 3).
"""

from __future__ import annotations

import pytest


class TestP2AdrDoesNotClaimDisplayNamesDeleted:
    """ADR-048 §5 must not claim _SOURCE_DISPLAY_NAMES is deleted."""

    def test_adr_048_does_not_claim_display_names_deleted(self) -> None:
        from pathlib import Path

        adr = Path(
            "docs/ADRs/048_declared_feature_aggregation_types.md"
        ).read_text()
        assert "`_SOURCE_DISPLAY_NAMES` are deleted" not in adr, (
            "ADR-048 §5 still claims '_SOURCE_DISPLAY_NAMES' is "
            "deleted, but it was retained for display purposes."
        )


class TestP6ConservationNotNoop:
    """Conservation must not be a silent no-op for direct callers."""

    @pytest.mark.xfail(
        reason="C-301: conservation no-op for direct callers without "
        "feature_agg_types — registered Tier 3, deferred",
    )
    def test_conservation_checks_something_without_types(
        self,
    ) -> None:
        from datafactory_adapters._conservation import (
            _extensive_indices,
        )

        feature_names = ["ged_sb_best", "acled_count", "gaul0_code"]
        indices = _extensive_indices(feature_names, None)
        assert len(indices) > 0, (
            "With feature_agg_types=None, _extensive_indices "
            "returns [] — conservation is a complete no-op. "
            "Direct callers of grid_to_country_month without "
            "feature_agg_types lose all conservation checking."
        )
