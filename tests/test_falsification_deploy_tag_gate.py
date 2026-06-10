"""Falsification stubs: claim 'we can move to deploy on server now.'

Audit 2026-06-10. Two findings:

P-1 (Soft): 5 tests fail on development — 1 version-bump gate
(test_version_not_already_tagged) and 4 partition alignment tests
(cross-repo drift between factory and views-models).

P-2 (Hard): No git tag exists for the new code. The deployment
procedure reads ~/.views-deploy-tag and checks out that exact tag.
Without a version bump + new tag, the server deploys v1.2.28
which does NOT include the skip logic.
"""

from __future__ import annotations

import subprocess

import pytest


class TestP2DeployRequiresNewTag:
    """P-2: deployment procedure requires a tag newer than v1.2.28."""

    @pytest.mark.xfail(reason="tag created at deploy time, not during development")
    def test_head_has_tag_after_v1228(self) -> None:
        """HEAD must have a tag newer than v1.2.28 to be
        deployable. The server checks out the tagged version."""
        result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "HEAD is not tagged. Deployment requires: "
            "bump version in pyproject.toml, "
            "git tag vX.Y.Z, git push origin vX.Y.Z"
        )
        tag = result.stdout.strip()
        assert tag != "v1.2.28", (
            f"HEAD is tagged {tag} — same as before skip logic. "
            f"Bump version first."
        )
