"""Falsification audit: production readiness for full UCDP consolidation.

Generated 2026-03-21 from falsification of the claim:
"The system is mature enough to produce a fully consolidated UCDP
dataset with a viewpoint corresponding to VIEWS production data."

FALSIFIED: Three hard falsifications — the .9 data stream has no
harvester, no consolidation support, and no survivorship strategy.
The system can only produce annual + candidate viewpoints, which
are missing ~13,000 events that production depends on.
"""

from __future__ import annotations

import pytest


class TestDot9HarvesterMissing:
    """Hard falsification: no .9 harvester exists."""

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: No ucdp_dot9.py harvester "
        "module exists. The system cannot harvest .9 data "
        "(YY.9.MM format) through its standard pipeline. "
        "Must create src/datafactory_harvester/sources/ucdp_dot9.py"
    )
    def test_dot9_harvester_exists(self) -> None:
        """The harvester has sources/ucdp_annual.py and
        sources/ucdp_candidate.py but no sources/ucdp_dot9.py.

        Without this module, the .9 data stream — which contains
        ~13,000 exclusive events not in any annual or candidate
        release — cannot be harvested programmatically.
        """
        pytest.fail("No .9 harvester module exists")


class TestDot9ConsolidationMissing:
    """Hard falsification: consolidator has no .9 support."""

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: UcdpConsolidationConfig has "
        "annual_dir and candidate_dir but no dot9_dir. The "
        "consolidator cannot read .9 Parquet files."
    )
    def test_consolidator_accepts_dot9(self) -> None:
        """UcdpConsolidationConfig needs a dot9_dir field and
        the consolidation loop needs to read from it, tagging
        records with _source_type='dot9'.
        """
        pytest.fail("Consolidator has no .9 support")


class TestDot9SurvivorshipMissing:
    """Hard falsification: no survivorship strategy handles .9."""

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: Only 'annual_wins' strategy "
        "exists. It treats everything non-annual as candidate. "
        "No strategy knows about _source_type='dot9'. The "
        "'production_parity' profile uses annual_wins — which "
        "cannot achieve production parity without .9 awareness."
    )
    def test_dot9_survivorship_strategy(self) -> None:
        """Need a survivorship strategy that handles three
        source types: annual > .9 > candidate. The current
        annual_wins strategy only distinguishes annual vs
        everything-else.
        """
        pytest.fail("No .9-aware survivorship strategy exists")


class TestProductionParityGaps:
    """Soft falsifications: known parity gaps."""

    @pytest.mark.skip(
        reason="SOFT FALSIFICATION: Summary event detection "
        "uses date_prec==5 but production uses "
        "(best>0 & span>1 & best>=span). Distribution uses "
        "exact division but production uses ceil()."
    )
    def test_summary_handling_matches_production(self) -> None:
        """Two known differences from production GedLoader:
        1. Detection: date_prec==5 vs (best>0 & span>1 & best>=span)
        2. Distribution: exact division vs np.int64(np.ceil(...))

        These produce different event counts and fatality totals
        for the ~1.4% of events that are summary events.
        """
        pytest.fail(
            "Summary event handling differs from production"
        )
