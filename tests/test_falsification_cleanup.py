"""Falsification audit: codebase cleanup completeness.

Generated 2026-03-22. All scaffolding retired:
smoke_test.py deleted, superseded reports deleted, session
artifacts cleaned, parity_test renamed to verify_parity,
uncommitted work committed.

FALSIFIED → SURVIVED after cleanup.
"""

from __future__ import annotations

import os


class TestCleanupResolved:

    def test_smoke_test_retired(self) -> None:
        """S1 resolved: smoke_test.py deleted."""
        path = os.path.join(
            os.path.dirname(__file__), "..",
            "scripts", "smoke_test.py",
        )
        assert not os.path.exists(path)

    def test_superseded_reports_removed(self) -> None:
        """S4 resolved: superseded reports deleted."""
        reports_dir = os.path.join(
            os.path.dirname(__file__), "..", "reports"
        )
        assert not os.path.exists(
            os.path.join(reports_dir, "rd_roadmap.md")
        )
        assert not os.path.exists(
            os.path.join(
                reports_dir, "product_development_plan.md"
            )
        )

    def test_parity_renamed(self) -> None:
        """S2 resolved: parity_test.py renamed to
        verify_parity.py.
        """
        scripts_dir = os.path.join(
            os.path.dirname(__file__), "..", "scripts"
        )
        assert not os.path.exists(
            os.path.join(scripts_dir, "parity_test.py")
        )
        assert os.path.exists(
            os.path.join(scripts_dir, "verify_parity.py")
        )

    def test_session_artifact_cleaned(self) -> None:
        """S6 resolved: resume_session.md deleted."""
        path = os.path.join(
            os.path.dirname(__file__), "..",
            "resume_session.md",
        )
        assert not os.path.exists(path)
