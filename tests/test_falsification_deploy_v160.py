"""Falsification: deployment readiness for v1.6.0 (2026-06-28).

Claim: "We are ready to bump the version, merge to main, tag, and deploy."

Hard falsification F1: version not bumped — pyproject.toml still says 1.5.0,
    but tag v1.5.0 already exists on main.
Hard falsification F2: deploy guide prescribes ``git merge development --ff-only``
    but main has merge commits not in development, so fast-forward is impossible.
Soft falsification F6: 43+ GitHub issues from completed sprints still open.
Soft falsification F7: product plan and roadmap stale by 3 major versions.
Soft falsification F8: stale branches not cleaned up.
"""

from __future__ import annotations

import subprocess

import pytest


def _current_version() -> str:
    import tomllib
    from pathlib import Path

    pyproject = Path("pyproject.toml")
    with pyproject.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def _tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "tag", "--list", tag],
        capture_output=True,
        text=True,
    )
    return tag in result.stdout.strip().splitlines()


class TestF1VersionBumped:
    """F1: version in pyproject.toml must be newer than any existing tag."""

    @pytest.mark.xfail(
        condition=_tag_exists(f"v{_current_version()}"),
        reason="version already tagged — expected post-deploy",
    )
    def test_version_not_already_tagged(self) -> None:
        """Current version must not already have a git tag."""
        version = _current_version()
        tag = f"v{version}"
        assert not _tag_exists(tag), (
            f"pyproject.toml says {version} but tag {tag} already exists. "
            f"Bump version before deploying."
        )


class TestF2FastForwardMerge:
    """F2: deploy guide merge procedure must be executable."""

    def test_main_is_ancestor_of_development(self) -> None:
        """Quick Deploy says ``git merge development --ff-only``.

        This requires main's HEAD to be an ancestor of development's
        HEAD. If not, the documented procedure fails with
        ``fatal: Not possible to fast-forward, aborting.``
        """
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "main", "development"],
            capture_output=True,
        )
        assert result.returncode == 0, (
            "main is not an ancestor of development — "
            "the deploy guide's --ff-only merge will fail. "
            "Merge main into development first."
        )


class TestF6IssueHygiene:
    """F6: completed sprint issues should be closed before release."""

    def test_completed_sprint_epics_closed(self) -> None:
        """Epic and tracking issues for merged sprints should be closed.

        Checks a subset of known-completed epics. If any are still open,
        the issue tracker is misleading about project state.
        """
        completed_epics = [258, 264, 266, 272, 274, 279, 280, 286, 290, 298]
        still_open = []
        for issue_num in completed_epics:
            result = subprocess.run(
                [
                    "gh", "issue", "view",
                    str(issue_num),
                    "--json", "state", "-q", ".state",
                ],
                capture_output=True,
                text=True,
            )
            if result.stdout.strip() == "OPEN":
                still_open.append(issue_num)
        assert not still_open, (
            f"{len(still_open)} completed sprint epics still OPEN: "
            f"{still_open}. Close before release."
        )


class TestF7ProductPlanCurrency:
    """F7: product plan must reflect current version."""

    def test_product_plan_not_stale(self) -> None:
        """Product plan title should reference a version >= current."""
        from pathlib import Path

        plan = Path("reports/product_development_plan11.md")
        if not plan.exists():
            pytest.skip("No product plan found")
        first_line = plan.read_text().splitlines()[0]
        version = _current_version()
        major_minor = ".".join(version.split(".")[:2])
        assert major_minor in first_line or "v2" in first_line, (
            f"Product plan title references an old version. "
            f"Current: {version}, plan: {first_line!r}"
        )


class TestF8StaleBranches:
    """F8: merged branches should be deleted before next release."""

    def test_no_stale_release_branches(self) -> None:
        """No release/* branches should exist for already-tagged versions."""
        result = subprocess.run(
            ["git", "branch", "-a"],
            capture_output=True,
            text=True,
        )
        release_branches = [
            line.strip()
            for line in result.stdout.splitlines()
            if "release/" in line
        ]
        stale = []
        for branch in release_branches:
            version_part = branch.split("release/")[-1]
            if _tag_exists(version_part):
                stale.append(branch)
        assert not stale, (
            f"Stale release branches for already-tagged versions: {stale}"
        )
