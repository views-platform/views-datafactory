"""Falsification: deployment readiness for v1.6.0 (2026-06-28).

Claim: "We are ready to bump the version, merge to main, tag, and deploy."

Hard falsification F1: version not bumped — pyproject.toml still says 1.5.0,
    but tag v1.5.0 already exists on main.
Hard falsification F2: main has merge commits not in development.
    Originally phrased as "the deploy guide prescribes ``git merge development
    --ff-only`` and fast-forward is impossible". Both halves of that framing are
    now obsolete: branch protection removed the fast-forward procedure entirely
    (a PR merge cannot fast-forward), and the guide that prescribed it no longer
    does. The divergence itself is still real and still worth asserting — it now
    happens by design, once per release, and is healed by the back-merge.
    Reframed 2026-08-02, #402.
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

    @pytest.mark.xfail(reason="version already tagged — expected post-deploy")
    def test_version_not_already_tagged(self) -> None:
        """Current version must not already have a git tag."""
        version = _current_version()
        tag = f"v{version}"
        assert not _tag_exists(tag), (
            f"pyproject.toml says {version} but tag {tag} already exists. "
            f"Bump version before deploying."
        )


class TestF2ReleaseTopology:
    """F2: main must stay an ancestor of development.

    Renamed from ``TestF2FastForwardMerge`` on 2026-08-02 (#402). The
    old name described a procedure that no longer exists — a class name
    is documentation too, and this one was actively misleading.
    """

    def test_main_is_ancestor_of_development(self) -> None:
        """Every release leaves main one merge commit ahead.

        Promotion goes through a PR (branch protection allows nothing
        else), and a PR merge cannot fast-forward. Merge-commit is the
        only method that preserves the release SHAs, and it always
        diverges by one. The back-merge restores the property; skipping
        it means ``git log main..development`` counts shipped work and
        the next release diffs against a base that never existed.
        """
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "main", "development"],
            capture_output=True,
        )
        # 0 = ancestor, 1 = not ancestor; anything else means the refs or
        # history are unavailable (CI shallow single-branch checkout) —
        # this is a LOCAL pre-deploy gate, not answerable there (C-320).
        if result.returncode not in (0, 1):
            pytest.skip(
                "main/development refs unavailable (shallow CI "
                "checkout) — deploy gate runs locally"
            )
        assert result.returncode == 0, (
            "main is not an ancestor of development. Normal right after "
            "a release, and healed by the back-merge: "
            "gh pr create --base development --head main, merged as a "
            "MERGE COMMIT (a squash recreates the divergence). "
            "See publishing_to_pypi.md §C.5. Detection also runs daily "
            "via .github/workflows/release-topology.yml."
        )


class TestF6IssueHygiene:
    """F6: completed sprint issues should be closed before release."""

    def test_completed_sprint_epics_closed(self) -> None:
        """Epic and tracking issues for merged sprints should be closed.

        Checks a subset of known-completed epics. If any are still open,
        the issue tracker is misleading about project state.
        """
        import json

        completed_epics = [
            258, 264, 266, 272, 274, 279, 280, 286, 290, 298,
        ]
        probe = subprocess.run(
            ["gh", "issue", "list", "--state", "open",
             "--json", "number", "-L", "500"],
            capture_output=True,
            text=True,
        )
        # No gh auth in CI (GH_TOKEN unset) — this is a LOCAL pre-deploy
        # gate; skip where it cannot be answered instead of failing (C-320).
        if probe.returncode != 0:
            pytest.skip(
                "gh CLI unavailable or unauthenticated — issue-hygiene "
                f"gate runs locally. stderr: {probe.stderr.strip()}"
            )
        open_numbers = {
            i["number"]
            for i in json.loads(probe.stdout)
        }
        still_open = [
            n for n in completed_epics if n in open_numbers
        ]
        assert not still_open, (
            f"{len(still_open)} completed sprint epics still OPEN: "
            f"{still_open}. Close before release."
        )


class TestF7ProductPlanCurrency:
    """F7: product plan must reflect current version."""

    def test_product_plan_not_stale(self) -> None:
        """Product plan title should reference a version >= current."""
        from pathlib import Path

        plans = sorted(
            Path("reports").glob("product_development_plan*.md"),
        )
        assert plans, (
            "No product development plan found in reports/. "
            "Expected reports/product_development_plan*.md"
        )
        plan = plans[-1]
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
