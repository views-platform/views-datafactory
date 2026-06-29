"""Falsification round 2: version bump + merge readiness (2026-06-29).

Claim: "We are ready to bump the version and merge to main."

Hard falsification DF-1: main/development divergence blocks ff-only.
Soft falsification DF-2: deployment guide omits merge-main-into-dev step.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class TestDF1MergeTopology:
    """ff-only merge requires main to be an ancestor of development."""

    def test_main_ancestor_of_development(self) -> None:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "main", "development"],
            capture_output=True,
        )
        assert result.returncode == 0, (
            "main is not an ancestor of development — "
            "run 'git merge main' on development before "
            "attempting 'git merge development --ff-only' on main"
        )

    def test_merge_main_into_development_is_conflict_free(self) -> None:
        merge_base = subprocess.check_output(
            ["git", "merge-base", "main", "development"],
            text=True,
        ).strip()
        result = subprocess.run(
            ["git", "merge-tree", merge_base, "development", "main"],
            capture_output=True, text=True,
        )
        assert not result.stdout.strip(), (
            "Merging main into development would produce conflicts: "
            f"{result.stdout[:200]}"
        )


class TestDF2DeployGuideCompleteness:
    """Deployment guide must document the merge-main-into-dev step."""

    def test_guide_mentions_merge_main_into_development(self) -> None:
        guide = Path("docs/guides/hetzner_deployment_guide.md")
        assert guide.exists(), "Deployment guide not found"
        content = guide.read_text().lower()
        has_merge_main = (
            "merge main into development" in content
            or "merge main" in content
            or "git merge main" in content
        )
        assert has_merge_main, (
            "Deployment guide does not mention merging main into "
            "development before ff-only merge. When GitHub PR merges "
            "create merge commits on main, --ff-only fails unless "
            "main is first merged into development."
        )
