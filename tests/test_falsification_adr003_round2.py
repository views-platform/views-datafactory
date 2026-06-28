"""Falsification stubs: ADR-003 compliance — round 2.

Source: /falsify 2026-06-28
Claim: "No surprises left" after addressing prior falsification findings.

Q2 (soft): grid_to_country_month.py:92 still uses prefix-based
    event feature identification — f.startswith(("ged_", "acled_")).
    CIC §5 line 60 documents this prefix behavior.
Q5 (soft): PR #299 body lists 5 commits but the 6th (c45b919,
    falsification fix) is missing.
"""

from __future__ import annotations

import pytest


class TestQ2NoPrefixCheckInExcludedCellWarning:
    """Excluded-cell warning should use declared types, not prefixes."""

    @pytest.mark.xfail(
        reason="C-302: grid_to_country_month.py:92 inline prefix check "
        "in excluded-cell warning — registered Tier 4, deferred",
    )
    def test_no_prefix_startswith_in_grid_to_country_month(self) -> None:
        from pathlib import Path

        src = Path(
            "src/datafactory_adapters/grid_to_country_month.py"
        ).read_text()
        assert 'startswith(("ged_"' not in src, (
            "grid_to_country_month.py:92 still uses "
            'f.startswith(("ged_", "acled_")) for the excluded-cell '
            "warning. Should use feature_agg_types to identify "
            "extensive features instead of prefix matching."
        )
