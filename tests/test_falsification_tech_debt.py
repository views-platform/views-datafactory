"""Falsification audit: tech debt cleanup completeness.

Generated 2026-03-22 from audit of the claim:
"All tech debt apart from the two deferred items (C-06, C-07)
have been identified and handled."

CONTESTED → SURVIVED after fixes. Three soft falsifications
found and resolved: error message hardcoded shape constant,
concerns00.md header was stale, maturity test skip was outdated.
"""

from __future__ import annotations


class TestTechDebtResolved:

    def test_smoke_test_retired(self) -> None:
        """Resolved: smoke_test.py retired. Its functionality
        is covered by layer scripts and 376 tests.
        """
        from pathlib import Path

        smoke_test = (
            Path(__file__).parent.parent
            / "scripts"
            / "smoke_test.py"
        )
        assert not smoke_test.exists(), (
            "smoke_test.py should have been deleted"
        )

    def test_concerns_header_accuracy(self) -> None:
        """Resolved: concerns file renamed to
        technical_risk_register.md and split into
        active + resolved archive (ADR-020).
        """
        from pathlib import Path

        old_file = (
            Path(__file__).parent.parent
            / "reports"
            / "concerns00.md"
        )
        assert not old_file.exists(), (
            "concerns00.md should be replaced by "
            "technical_risk_register.md"
        )

        register = (
            Path(__file__).parent.parent
            / "reports"
            / "technical_risk_register.md"
        )
        assert register.exists(), (
            "technical_risk_register.md not found"
        )
        content = register.read_text()
        assert "74 concerns total" in content
        assert "38 resolved" in content

    def test_maturity_skip_reason_current(self) -> None:
        """Resolved: maturity test for .9 in smoke test
        converted from stale skip to passing assertion.
        """
        from pathlib import Path

        maturity_test = (
            Path(__file__).parent
            / "test_falsification_maturity.py"
        )
        content = maturity_test.read_text()
        # Should not have the stale skip reason
        assert "has zero .9 references" not in content
