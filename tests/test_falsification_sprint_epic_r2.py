"""Falsification stubs: Sprint epic #205 readiness — round 2.

Source: /falsify "we're 100% ready to execute the Sprint epic" (round 2, 2026-06-18)

Hard falsification:
  R2 — F8b xfail fix uncommitted: test_falsification_deploy_v130.py modified
        but not committed or pushed to origin.
"""

from __future__ import annotations

import subprocess


class TestR2DeployXfailCommitted:
    """The F8b fix (deploy v1.3.0 xfail) must be committed and pushed."""

    def test_deploy_v130_test_not_modified(self) -> None:
        result = subprocess.run(
            ["git", "diff", "--name-only",
             "tests/test_falsification_deploy_v130.py"],
            capture_output=True, text=True,
        )
        assert not result.stdout.strip(), (
            "tests/test_falsification_deploy_v130.py has uncommitted changes — "
            "the F8b xfail fix needs to be committed and pushed"
        )
