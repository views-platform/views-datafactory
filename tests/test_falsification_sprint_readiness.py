"""Falsification stubs: sprint readiness for WDI Readiness Gate.

Source: /falsify "we are ready to start the epic sprint" (2026-06-19)

Hard falsifications:
  F1 — PR #207 (review-rr strategic curation) not merged into development

Soft falsifications:
  F6 — Register edits from expert-code-review (D-40, C-252/C-257 notes)
        uncommitted on feature/shdi-downstream, absent from development
"""

from __future__ import annotations

import subprocess

import pytest

pytestmark = pytest.mark.falsification


class TestF1PrerequisitePRMerged:
    """PR #207 must be merged before the sprint branch is created."""

    def test_pr207_merged_into_development(self) -> None:
        result = subprocess.run(
            ["gh", "pr", "view", "207", "--json", "state", "--jq", ".state"],
            capture_output=True,
            text=True,
            check=True,
        )
        state = result.stdout.strip()
        assert state == "MERGED", (
            f"PR #207 is {state}, not MERGED. "
            "Sprint plan requires PR #207 merged before creating "
            "feature/sprint-wdi-readiness-gate from development."
        )


class TestF6RegisterEditsOnDevelopment:
    """Register edits from expert-code-review must reach development."""

    def test_d40_exists_on_development(self) -> None:
        result = subprocess.run(
            [
                "git", "show",
                "development:reports/technical_risk_register.md",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "D-40" in result.stdout, (
            "D-40 (DGP check module placement) not found on development. "
            "Register edits from expert-code-review are uncommitted on "
            "feature/shdi-downstream and absent from development."
        )

    def test_disagreement_count_9_on_development(self) -> None:
        result = subprocess.run(
            [
                "git", "show",
                "development:reports/technical_risk_register.md",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "9 open disagreements" in result.stdout, (
            "Development register still says 8 open disagreements. "
            "Header update (8→9) from D-40 registration not on development."
        )
