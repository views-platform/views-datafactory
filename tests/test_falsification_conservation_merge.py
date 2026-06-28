"""Falsification stubs: conservation hardening merge readiness.

Source: /falsify 2026-06-24
Claim: PR #265 is 100% ready to merge.
Verdict: FALSIFIED (2 hard).

F-1 (hard): CIC grid_to_country_month §5 does not document the new
    intensive feature UserWarning added in this PR.
F-2 (hard): CIC grid_to_country_month §2 non-goal claims the module
    "does not validate that the grid contains meaningful data
    (non-zero, non-NaN)" — but it now does, via assert_cm_conservation
    calling assert_no_unexpected_nan for extensive features.
"""

from __future__ import annotations

from pathlib import Path


class TestF1CicIntensiveBehavior:
    """CIC §5 (Outputs and Side Effects) must document
    intensive feature handling (ADR-048)."""

    def test_cic_mentions_intensive(self) -> None:
        cic = Path("docs/CICs/grid_to_country_month.md").read_text()
        section5_start = cic.index("## 5.")
        section6_start = cic.index("## 6.")
        section5 = cic[section5_start:section6_start]
        assert "intensive" in section5.lower(), (
            "CIC §5 does not mention intensive feature handling. "
            "The module raises ValueError for intensive features "
            "when feature_agg_types is provided (ADR-048)."
        )


class TestF2CicNanNonGoal:
    """CIC §2 (Non-Goals) claims the module does not validate
    non-NaN data, but assert_cm_conservation now does."""

    def test_cic_nongoal_updated_for_nan_validation(self) -> None:
        cic = Path("docs/CICs/grid_to_country_month.md").read_text()
        section2_start = cic.index("## 2.")
        section3_start = cic.index("## 3.")
        section2 = cic[section2_start:section3_start]
        assert "non-NaN" not in section2 or "extensive" in section2, (
            "CIC §2 still says the module 'does not validate that "
            "the grid contains meaningful data (non-zero, non-NaN)' "
            "but assert_cm_conservation now calls "
            "assert_no_unexpected_nan which rejects NaN in "
            "extensive feature columns. The non-goal must be "
            "qualified or removed."
        )
