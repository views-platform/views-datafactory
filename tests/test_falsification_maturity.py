"""Falsification audit: system maturity for full UCDP production.

Generated 2026-03-21 from re-audit of the claim:
"The system is mature enough to produce fully consolidated UCDP
data with a viewpoint corresponding to VIEWS production."

CONTESTED: No hard falsifications. One soft falsification:
full-scale consolidation untested. Two prior soft falsifications
resolved: smoke test now exercises .9, stale stubs cleaned.
"""

from __future__ import annotations

import pytest


class TestMaturitySoftFalsifications:

    def test_smoke_test_exercises_dot9(self) -> None:
        """Resolved: smoke test step 3/10 now exercises .9
        harvest, and step 5/10 consolidates all three sources
        including .9. The production_parity profile (dot9_wins
        + ceil_split) is used in step 7/10.
        """
        from pathlib import Path

        smoke_test = Path(__file__).parent.parent / "scripts" / "smoke_test.py"
        content = smoke_test.read_text()
        assert "ucdp_dot9" in content, (
            "Smoke test should reference ucdp_dot9"
        )
        assert "production_parity" in content, (
            "Smoke test should use production_parity profile"
        )

    @pytest.mark.skip(
        reason="SOFT FALSIFICATION: The claim says 'fully "
        "consolidated from start to Feb 2026' but we have "
        "only 16 of ~197 available source files. The full "
        "candidate history (84 versions) and full .9 history "
        "(98 versions) have never been harvested or "
        "consolidated together."
    )
    def test_full_scale_consolidation(self) -> None:
        """Full-scale consolidation with all available data
        has never been tested. Parity was proven on one .9
        version, not the full 8-year history.
        """
        pytest.fail("Full-scale consolidation untested")

    def test_stale_stubs_cleaned(self) -> None:
        """Resolved: test_falsification_production_readiness.py
        was deleted (commit c01b72b) after M1-M4 resolved all
        4 stubs it contained (.9 harvester, dot9_dir, dot9_wins,
        ceil_split).
        """
        import os

        path = os.path.join(
            os.path.dirname(__file__),
            "test_falsification_production_readiness.py",
        )
        assert not os.path.exists(path), (
            "Stale file should have been deleted"
        )
