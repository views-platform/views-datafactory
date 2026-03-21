"""Falsification audit: .9 investigation claims.

Generated 2026-03-21 from falsification of the claim:
"We now have the full picture of .9 vs individual candidate datasets."

These test stubs document findings that need to be addressed.
They are intentionally FAILING until the underlying issues are resolved.
"""

from __future__ import annotations

import pytest


class TestDot9InvestigationFalsifications:
    """Hard and soft falsifications from the .9 investigation audit."""

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: ADR-015 says .9 'stitches annual "
        "and candidate' but .9 contains 13,005 events not in any "
        "annual or candidate release. ADR-015 must be updated."
    )
    def test_adr015_stitching_claim_is_false(self) -> None:
        """ADR-015 line 18 claims .9 'stitches annual and candidate.'

        Empirically disproven: 13,005 events in .9 (25.9.11) are
        not in annual v25.1 (1989-2024) or any candidate version
        (24.0.1-26.0.2). Checked 26 candidate versions total.

        Fix: Update ADR-015 to reflect that .9 is a distinct data
        source with exclusive content, not a consolidation of
        public API data.
        """
        pytest.fail("ADR-015 stitching claim is empirically false")

    @pytest.mark.skip(
        reason="SOFT FALSIFICATION: findings.md states .9 versions "
        "available '25.9.1 through 26.9.2' but .9 exists from "
        "18.9.1 onward — 84 additional versions undocumented."
    )
    def test_dot9_availability_understated(self) -> None:
        """findings.md section 1.1 says 'Versions confirmed
        available: 25.9.1 through 26.9.2.'

        Empirically: .9 versions exist from 18.9.1 through 26.9.2
        with data in every month probed. 98+ monthly versions
        spanning 8 years, each containing 11K-33K events.

        Fix: Update findings.md to reflect full .9 availability.
        """
        pytest.fail(
            "findings.md understates .9 availability by 84 versions"
        )


class TestDot9BonusObservations:
    """Bonus observations discovered during falsification."""

    @pytest.mark.skip(
        reason="OBSERVATION: Candidate data is mutable. 26.0.1 "
        "changed from 727 to 1,727 events between fetches. "
        "Snapshot comparisons are time-sensitive."
    )
    def test_candidate_data_is_mutable(self) -> None:
        """Candidate versions are updated in place by UCDP.

        26.0.1: 727 events (first fetch) → 1,727 events (later)
        26.0.2: 298 events (first fetch) → 1,298 events (later)

        This means our "exclusive" count of 13,005 could change
        if candidates are updated to include more events.
        Our provenance system should track fetch timestamps.
        """
        pytest.fail("Candidate data mutability not documented")
