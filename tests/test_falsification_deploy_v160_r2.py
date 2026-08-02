"""Falsification round 2: version bump + merge readiness (2026-06-29).

Claim: "We are ready to bump the version and merge to main."

Hard falsification DF-1: main and development have diverged.
Soft falsification DF-2: the release guide omits the back-merge step.

Rationale updated 2026-08-02 (#402). These probes were written when
promotion was a local ``git merge development --ff-only``, so DF-1 was
"divergence blocks ff-only". Branch protection ended that procedure:
both branches require a pull request, admins included, and a PR merge
cannot fast-forward. Promotion is now a merge commit, which diverges by
exactly one commit *every* release.

The assertions did not change, because the invariant did not. What
changed is why it matters: not "so ff-only works", but so
``git log main..development`` keeps counting only unreleased work, and
so each release's diff starts from a base that reflects what shipped.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


class TestDF1MergeTopology:
    """main must remain an ancestor of development.

    Every release leaves one merge commit on main that development has
    not seen. Back-merging restores the property; skipping it lets the
    branches drift a little further each time.
    """

    def test_main_ancestor_of_development(self) -> None:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "main", "development"],
            capture_output=True,
        )
        # 0 = ancestor, 1 = not; other codes mean refs/history missing
        # (CI shallow checkout) — local pre-deploy gate, skip there (C-320).
        if result.returncode not in (0, 1):
            pytest.skip(
                "main/development refs unavailable (shallow CI "
                "checkout) — deploy gate runs locally"
            )
        assert result.returncode == 0, (
            "main is not an ancestor of development. Expected right "
            "after a release: promotion leaves a merge commit on main "
            "that development has not seen. Fix with the back-merge — "
            "gh pr create --base development --head main — merged as a "
            "MERGE COMMIT, never a squash (a squash creates yet another "
            "commit that is not main). See publishing_to_pypi.md §C.5."
        )

    def test_merge_main_into_development_is_conflict_free(self) -> None:
        try:
            merge_base = subprocess.check_output(
                ["git", "merge-base", "main", "development"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except subprocess.CalledProcessError:
            pytest.skip(
                "main/development refs unavailable (shallow CI "
                "checkout) — deploy gate runs locally"
            )
        result = subprocess.run(
            ["git", "merge-tree", merge_base, "development", "main"],
            capture_output=True, text=True,
        )
        assert not result.stdout.strip(), (
            "Merging main into development would produce conflicts: "
            f"{result.stdout[:200]}"
        )


class TestDF2ReleaseGuideCompleteness:
    """The release guide must document the back-merge.

    Retargeted 2026-08-02 (#402). This probe used to read
    ``hetzner_deployment_guide.md``, which carried a second copy of the
    release ritual. That copy prescribed ``git merge development
    --ff-only`` and ``git push origin development`` — both forbidden by
    branch protection since 2026-07-31 — and the two copies had drifted
    apart without anything noticing. The ritual now lives in exactly one
    place, so the probe follows it there.
    """

    GUIDE = Path("docs/guides/publishing_to_pypi.md")

    def test_release_guide_documents_the_back_merge(self) -> None:
        assert self.GUIDE.exists(), f"{self.GUIDE} not found"
        content = self.GUIDE.read_text().lower()
        assert "--base development --head main" in content, (
            "The release guide does not show the back-merge command. "
            "Promotion leaves a merge commit on main that development "
            "has not seen; without this step the branches diverge a "
            "little further after every release."
        )
        assert "never squash" in content or "never a squash" in content, (
            "The release guide shows the back-merge but does not warn "
            "against squashing it. A squash creates another commit that "
            "is not main, so main still is not an ancestor — the step "
            "looks done and achieves nothing."
        )

    def test_server_guide_does_not_carry_a_runnable_second_copy(self) -> None:
        """The duplication is the defect, not the stale wording.

        Checks fenced code blocks only. Prose that *names* the dead
        commands in order to say "these cannot be run any more" is the
        point — a reader who remembers them needs to be told why they
        are gone, or they will reinstate them. What must not come back
        is a **runnable** copy, and runnable means inside a fence.
        """
        server_guide = Path("docs/guides/hetzner_deployment_guide.md")
        assert server_guide.exists(), "Server guide not found"

        code = "\n".join(
            re.findall(r"^```.*?^```", server_guide.read_text(), re.M | re.S)
        )
        for forbidden, why in (
            (
                "git merge development --ff-only",
                "a PR merge cannot fast-forward, so this can never run",
            ),
            (
                "git push origin development",
                "development requires a PR; admins are not exempt",
            ),
        ):
            assert forbidden not in code, (
                f"hetzner_deployment_guide.md has a runnable "
                f"{forbidden!r} in a code block — {why}. The release "
                f"ritual lives in publishing_to_pypi.md and only there; "
                f"a second copy is how the two guides drifted apart "
                f"(#402)."
            )
