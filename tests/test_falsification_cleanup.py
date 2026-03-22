"""Falsification audit: codebase cleanup completeness.

Generated 2026-03-22 from audit of the claim:
"All tech debt, temporary scaffolding, leftover audits, and
outdated side quests have been cleaned up."

FALSIFIED: 3 hard falsifications, 3 soft falsifications.
smoke_test.py still exists, superseded reports not removed,
uncommitted shapefile work in working tree.
"""

from __future__ import annotations

import pytest


class TestCleanupHardFalsifications:

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: scripts/smoke_test.py "
        "still exists (19KB). It's a 10-step development "
        "test script whose functionality is covered by the "
        "layer scripts and 320+ tests. Temporary scaffolding "
        "never retired."
    )
    def test_smoke_test_retired(self) -> None:
        pytest.fail("smoke_test.py not retired")

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: reports/rd_roadmap.md "
        "and reports/product_development_plan.md still exist "
        "alongside their _01 successors which say 'Supersedes'. "
        "Dead documents that can mislead readers."
    )
    def test_superseded_reports_removed(self) -> None:
        pytest.fail("Superseded reports not removed")

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: Uncommitted shapefile "
        "harvester config changes in working tree — modified "
        "files + untracked CIC + test. Temporary by definition."
    )
    def test_no_uncommitted_work(self) -> None:
        pytest.fail("Uncommitted changes in working tree")


class TestCleanupSoftFalsifications:

    @pytest.mark.skip(
        reason="SOFT FALSIFICATION: scripts/parity_test.py "
        "still exists. One-time .9 investigation script. "
        "Investigation complete (100% match). Could be "
        "retained as re-runnable audit but is currently "
        "an investigation artifact."
    )
    def test_parity_test_status(self) -> None:
        pytest.fail("parity_test.py status unclear")

    @pytest.mark.skip(
        reason="SOFT FALSIFICATION: scripts/generate_schema_ref.py "
        "and scripts/visualize_grid.py are development "
        "utilities, not production operational scripts."
    )
    def test_utility_scripts_status(self) -> None:
        pytest.fail("Utility scripts not categorized")

    @pytest.mark.skip(
        reason="SOFT FALSIFICATION: resume_session.md is a "
        "session artifact in the repo root. Not production "
        "code. Should be in .gitignore or deleted."
    )
    def test_session_artifacts_cleaned(self) -> None:
        pytest.fail("Session artifacts remain")
