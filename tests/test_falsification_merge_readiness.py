"""Falsification stubs: development→main merge readiness.

Source: /falsify audit 2026-05-27
Claim: development can be merged into main with minimal risk
       of regression.
Verdict: FALSIFIED (1 hard).

F-1 (hard): test_falsification_v1221_cleanup.py searches only the
    first 2000 characters of the register for "N open concerns",
    but the Source line on development has grown to push that
    string to char 2012. The test passes locally only because
    the working tree has an uncommitted fix (2000→3000). Merging
    PR #69 without committing the fix puts a guaranteed test
    failure on main.
"""

from __future__ import annotations

from pathlib import Path


class TestF1RegisterSearchWindow:
    """The register header search window must be wide enough
    to find 'N open concerns' despite Source-line growth."""

    def test_open_concerns_within_search_window(self) -> None:
        """Regression guard: 'open concerns' must be findable
        within the search window used by
        test_falsification_v1221_cleanup.py."""
        register = Path(
            "reports/technical_risk_register.md"
        ).read_text()
        idx = register.find("open concerns")
        assert idx != -1, (
            "Register has no 'open concerns' string at all"
        )
        assert idx < 6000, (
            f"'open concerns' is at char {idx}, which exceeds "
            f"the 6000-char search window in "
            f"test_falsification_v1221_cleanup.py. "
            f"The Source line has grown too long — either "
            f"trim it or widen the search window."
        )
