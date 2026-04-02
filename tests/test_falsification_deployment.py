"""Falsification audit: deployment quality.

Claim: "We are at deployment level quality."

FALSIFIED — 1 hard falsification, 3 soft falsifications:
  F1 (hard): D-03 is Tier 1 with open gap, contradicts deployment readiness
  F2 (soft): development 35 commits ahead of main; server runs development
  F3 (soft): HTTP only — credentials in cleartext on wire
  F5 (soft): no deployment gate between push and server
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.falsification()
class TestDeploymentQuality:

    def test_tier1_items_resolved(self) -> None:
        """F1: no open Tier 1 items should remain for deployment.

        D-03 has a remaining gap (no freshness indicator). Either
        resolve it or reclassify the trigger to match actual
        deployment scope (single-user research, not multi-consumer).
        """
        register = (
            Path(__file__).parent.parent
            / "reports"
            / "technical_risk_register.md"
        )
        content = register.read_text()
        # Find Tier 1 section and check for unresolved items
        lines = content.split("\n")
        in_tier1 = False
        open_tier1 = []
        for line in lines:
            if "## Tier 1" in line:
                in_tier1 = True
                continue
            if in_tier1 and line.startswith("## Tier"):
                break
            if (
                in_tier1
                and line.startswith("### ")
                and "~~" not in line
                and "RESOLVED" not in line
            ):
                open_tier1.append(line.strip())

        assert not open_tier1, (
            f"Open Tier 1 items block deployment: {open_tier1}"
        )

    def test_main_branch_not_stale(self) -> None:
        """F2: main should not be more than 5 commits behind
        development after a deployment milestone.
        """
        import subprocess

        result = subprocess.run(
            ["git", "log", "--oneline", "main..development"],
            capture_output=True, text=True, check=False,
        )
        n_ahead = len(result.stdout.strip().split("\n"))
        assert n_ahead <= 5, (
            f"development is {n_ahead} commits ahead of main. "
            f"Merge to main before claiming deployment quality."
        )
