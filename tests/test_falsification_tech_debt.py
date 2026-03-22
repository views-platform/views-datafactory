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

    def test_error_message_uses_shape_constant(self) -> None:
        """Resolved: smoke_test.py error message now
        interpolates _EXPECTED_REAL_SHAPE instead of
        hardcoding (259200, 48, 2).
        """
        from pathlib import Path

        smoke_test = (
            Path(__file__).parent.parent
            / "scripts"
            / "smoke_test.py"
        )
        content = smoke_test.read_text()
        # The error message should reference the constant
        assert "_EXPECTED_REAL_SHAPE" in content
        # No hardcoded shape tuple in error messages
        lines = content.splitlines()
        for line in lines:
            if "expected (259200" in line:
                msg = f"Hardcoded shape in: {line.strip()}"
                raise AssertionError(msg)

    def test_concerns_header_accuracy(self) -> None:
        """Resolved: concerns00.md header updated to
        reflect actual counts (24 resolved, 1 documented,
        2 deferred, 8 open, 2/4 disagreements resolved).
        """
        from pathlib import Path

        concerns = (
            Path(__file__).parent.parent
            / "reports"
            / "concerns00.md"
        )
        content = concerns.read_text()
        # Header should NOT claim 27 resolved
        assert "27 of 35" not in content, (
            "Stale header: actual resolved count is 24"
        )
        # Header should reflect accurate counts
        assert "24 of 35" in content

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
