"""Falsification audit: system maturity for full UCDP production.

Generated 2026-03-21 from re-audit of the claim:
"The system is mature enough to produce fully consolidated UCDP
data with a viewpoint corresponding to VIEWS production."

CONTESTED: No hard falsifications. Three soft falsifications:
smoke test doesn't exercise .9, full-scale consolidation untested,
and prior falsification stubs are stale.
"""

from __future__ import annotations

import pytest


class TestMaturitySoftFalsifications:

    @pytest.mark.skip(
        reason="SOFT FALSIFICATION: The smoke test "
        "(scripts/smoke_test.py) has zero .9 references. "
        "It exercises annual + candidate but never tests "
        "the production_parity profile or .9 data path. "
        "The parity test (scripts/parity_test.py) exists "
        "but is separate and not part of routine testing."
    )
    def test_smoke_test_exercises_dot9(self) -> None:
        """The primary smoke test should exercise the .9
        data path since production depends on it.
        """
        pytest.fail("Smoke test does not exercise .9")

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

    @pytest.mark.skip(
        reason="SOFT FALSIFICATION: All 4 stubs in "
        "test_falsification_production_readiness.py are "
        "stale — they claim issues resolved by M1-M4. "
        "The stubs should be removed or converted to "
        "passing tests documenting the fix."
    )
    def test_stale_falsification_stubs(self) -> None:
        """test_falsification_production_readiness.py has 4
        stubs claiming: no .9 harvester, no dot9_dir, no
        dot9_wins, no ceil_split. All resolved.
        """
        pytest.fail(
            "4 stale falsification stubs mislead readers"
        )
