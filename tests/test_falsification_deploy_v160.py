"""Falsification: deployment readiness for v1.6.0 (2026-06-28).

Claim: "We are ready to bump the version, merge to main, tag, and deploy."

Hard falsification F1: REMOVED 2026-08-11 (#425). It asserted "the version
    is not already tagged", which cannot fail in this repo — version is bumped
    only at release time, so between releases the version is always a tag that
    exists. Replaced by TestVersionMatchesItsTag, which asserts the half that
    can fail, plus an unskippable guard in publish_package.yml. See C-346.
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


def _head_tag() -> str | None:
    """The ``v*`` tag HEAD sits exactly on, or None."""
    result = subprocess.run(
        ["git", "describe", "--tags", "--exact-match", "HEAD"],
        capture_output=True,
        text=True,
    )
    tag = result.stdout.strip()
    return tag if result.returncode == 0 and tag.startswith("v") else None


class TestVersionMatchesItsTag:
    """The released version must equal the tag it was released under (#363).

    **Replaces ``TestF1VersionBumped``, deleted 2026-08-11 (#425).** That
    class asserted "the current version is not already tagged", and it
    could not fail. Version here is bumped only at release time, so from
    the moment a release lands until the next bump the version *is* a tag
    that exists — the whole inter-release period. Hence its unconditional
    ``xfail``. Measured before removing it:

    ===================  ======================  ===========
    version tagged?      result                  suite exit
    ===================  ======================  ===========
    yes (steady state)   XFAIL                   0
    no  (just bumped)    XPASS                   0
    ===================  ======================  ===========

    Green either way. It asked *"have you bumped yet?"*, which repo state
    cannot answer, because "about to release" is not knowable from the
    repo — only from the tag that triggers a release. That question is
    now answered where it can be: `publish_package.yml` compares
    ``github.ref_name`` to the version, before the build, unskippably.

    What IS answerable here is the other half: **if HEAD is on a tag, the
    version must match it.** That can fail, and does — drilled by setting
    the version away from the tag.

    Four sibling copies of the deleted assertion survive in
    ``test_falsification_{deploy_v130,ghspop_deploy_v2,ghsbuilts_deploy_v2}``
    and ``test_falsification_vdem_deploy``. They use a *conditional*
    ``xfail`` that looks more rigorous and is not: it runs only when the
    version is untagged, then asserts the version is untagged — asserting
    the condition that selected it. Left in place deliberately; removing
    four more classes is beyond this story. Registered as **C-346**.
    """

    def test_version_equals_the_tag_head_is_on(self) -> None:
        tag = _head_tag()
        if tag is None:
            pytest.skip(
                "HEAD is not on a v* tag — there is no tag to compare "
                "against, and guessing one would be worse than saying so "
                "(C-320). The unskippable half of this check lives in "
                "publish_package.yml, where the triggering tag is known."
            )
        version = _current_version()
        assert tag == f"v{version}", (
            f"HEAD is on tag {tag} but pyproject.toml declares version "
            f"{version} (expected tag v{version}). A release published "
            f"from this state puts a wheel on PyPI whose metadata "
            f"disagrees with the git history, discoverable only by "
            f"comparing them by hand. v* tags are immutable under the "
            f"tag ruleset, so the fix is to bump pyproject.toml — the "
            f"tag cannot be moved."
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
    """F8: merged branches should be deleted before next release.

    Local branches and remote branches are checked from different
    sources, deliberately. The original version used ``git branch -a``,
    which folds in **remote-tracking refs** — a local cache that goes
    stale the moment someone else deletes a branch, and that only
    ``git fetch --prune`` refreshes.

    That made the gate fail against a repository which was actually
    clean. Observed 2026-08-03: `delete_branch_on_merge` had removed
    every merged branch on the remote, yet this test failed because the
    local clone had been fetched without ``--prune`` all session. Nine
    local branches were deleted chasing a problem that did not exist.

    A gate that reddens for reasons unrelated to what it asserts stops
    being read — that is C-320. So remote state is now taken from the
    remote (``git ls-remote``), which is authoritative, and the test
    skips rather than guesses when the network cannot answer.
    """

    @staticmethod
    def _stale(names: list[str]) -> list[str]:
        return [
            n for n in names
            if "release/" in n and _tag_exists(n.split("release/")[-1])
        ]

    def test_no_stale_local_release_branches(self) -> None:
        """Local ``release/*`` branches for tagged versions are leftovers.

        Skipped on CI, deliberately. This asserts a property of *an
        operator's clone*, and a fresh runner is not one: ``actions/
        checkout`` leaves exactly one local branch, so the assertion is
        trivially true there. A gate that passes because there is
        nothing to look at is worse than one that skips — it reports
        coverage it does not have. Same idiom as the remote check below
        and as C-320: skip where the environment cannot answer.
        """
        import os

        if os.environ.get("CI"):
            pytest.skip(
                "local-clone hygiene is not answerable on a fresh CI "
                "runner — actions/checkout leaves one local branch, so "
                "this would pass without inspecting anything. The remote "
                "half of this class DOES run in CI."
            )
        result = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            capture_output=True,
            text=True,
        )
        stale = self._stale(
            [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        )
        assert not stale, (
            f"Stale LOCAL release branches for already-tagged versions: "
            f"{stale}. Delete with `git branch -D <name>`. These are your "
            f"own leftovers — the remote is checked separately."
        )

    def test_no_stale_remote_release_branches(self) -> None:
        """Asks the remote, not the local cache of it."""
        probe = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", "refs/heads/release/*"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            pytest.skip(
                "cannot reach origin — remote branch state is not "
                "answerable offline; local gate above still applies "
                "(C-320: skip where the environment cannot answer)"
            )
        names = [
            ln.split("refs/heads/", 1)[1]
            for ln in probe.stdout.splitlines()
            if "refs/heads/" in ln
        ]
        stale = self._stale(names)
        assert not stale, (
            f"Stale release branches ON THE REMOTE for already-tagged "
            f"versions: {stale}. `delete_branch_on_merge` should have "
            f"removed these; if it did not, the repo setting may have been "
            f"turned off. Note this reads the remote directly, so a stale "
            f"local `remotes/origin/...` ref cannot cause this failure — "
            f"run `git fetch --prune` to tidy your own view."
        )
