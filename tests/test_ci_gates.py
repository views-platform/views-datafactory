"""Guard: the CI checks added for C-341/C-342 keep their preconditions.

Both checks in this file are load-bearing on **ordering**, and in both
cases getting the order wrong produces a *green* run rather than a red
one. That is the whole reason they are asserted rather than trusted.

``uv lock --check`` must precede ``uv sync``
    ``uv sync`` rewrites ``uv.lock`` when ``pyproject.toml`` has moved.
    Placed after it, the check inspects a lockfile CI has already
    repaired and passes unconditionally (C-342).

Creating local ``main``/``development`` refs must precede the gates
    ``actions/checkout`` leaves exactly one local branch, so the deploy
    gates' bare ``git merge-base --is-ancestor main development`` exits
    128 and they **skip themselves**. Measured, not assumed: a simulated
    runner checkout returns 128 even at ``fetch-depth: 0``. Remove those
    two ``git branch -f`` lines while "tidying" and the gates go on
    reporting success while asserting nothing — C-341 restored, silently.

**Why the parse is not enough.** These were nearly shipped with a
duplicate ``run:`` key in the same YAML step, produced by a bad
insertion. ``yaml.safe_load`` accepted it — PyYAML takes the last
duplicate silently — so a syntax check said "parses" while the lock
check had been overwritten by ``uv sync`` and would never have run. The
structural assertions below are what catches that; a parse is not a
verification (C-345).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
CI = REPO / ".github" / "workflows" / "ci.yml"
HYGIENE = REPO / ".github" / "workflows" / "release-topology.yml"


def _steps(workflow: Path, job: str) -> list[dict[str, Any]]:
    data = yaml.safe_load(workflow.read_text())
    assert job in data["jobs"], f"{workflow.name} has no job {job!r}"
    return data["jobs"][job]["steps"]


def _index_of_run(steps: list[dict[str, Any]], needle: str) -> int:
    for i, step in enumerate(steps):
        run = step.get("run") or ""
        if needle in run:
            return i
    raise AssertionError(f"no step runs {needle!r}")


class TestEveryStepIsWellFormed:
    """A step with two `run:` keys parses fine and silently loses one."""

    def test_no_step_has_both_or_neither_run_and_uses(self) -> None:
        for workflow in (CI, HYGIENE):
            data = yaml.safe_load(workflow.read_text())
            for job_name, job in data["jobs"].items():
                for step in job["steps"]:
                    label = step.get("name") or step.get("uses") or step
                    has_run = "run" in step
                    has_uses = "uses" in step
                    problem = (
                        "both run and uses" if has_run else "neither run nor uses"
                    )
                    assert has_run != has_uses, (
                        f"{workflow.name}:{job_name} step {label!r} has "
                        f"{problem}. "
                        f"A malformed step can still parse — this one was "
                        f"caught after `yaml.safe_load` reported success on a "
                        f"step with a duplicate `run:` key, where PyYAML "
                        f"silently kept the last."
                    )


class TestLockCheckRunsBeforeSync:
    def test_uv_lock_check_is_in_the_test_job(self) -> None:
        runs = [s.get("run") or "" for s in _steps(CI, "test")]
        assert any("uv lock --check" in r for r in runs), (
            "The `test` job no longer runs `uv lock --check`. Without it a "
            "pull request that edits pyproject.toml without re-locking goes "
            "green: `uv sync` repairs uv.lock in CI's own checkout, tests the "
            "repaired version, discards it, and the stale lock stays in git "
            "(C-342)."
        )

    def test_it_precedes_uv_sync(self) -> None:
        steps = _steps(CI, "test")
        assert _index_of_run(steps, "uv lock --check") < _index_of_run(
            steps, "uv sync"
        ), (
            "`uv lock --check` must run BEFORE `uv sync`. After it, the check "
            "inspects a lockfile that `uv sync` has already repaired, so it "
            "passes unconditionally — a green tick that verifies nothing."
        )


class TestDeployGatesCanActuallyAnswer:
    def test_local_refs_are_created_before_the_gates_run(self) -> None:
        steps = _steps(HYGIENE, "topology")
        refs = _index_of_run(steps, "git branch -f main origin/main")
        gates = _index_of_run(steps, "test_falsification_deploy_v160")
        assert refs < gates, (
            "The step creating local `main`/`development` refs must run "
            "before the deploy gates. `actions/checkout` leaves one local "
            "branch, so without those refs `git merge-base --is-ancestor "
            "main development` exits 128 and the topology gates SKIP "
            "themselves — reporting success while asserting nothing, which "
            "is C-341 exactly."
        )

    def test_the_gates_get_a_token_and_the_ci_marker(self) -> None:
        steps = _steps(HYGIENE, "topology")
        gates = steps[_index_of_run(steps, "test_falsification_deploy_v160")]
        env = gates.get("env") or {}
        assert "GH_TOKEN" in env, (
            "The gate step needs GH_TOKEN or TestF6IssueHygiene skips "
            "instead of querying the issue tracker."
        )
        assert env.get("CI"), (
            "The gate step needs CI set so TestF8StaleBranches' local half "
            "skips rather than passing trivially — a fresh runner has one "
            "local branch, so it would otherwise claim coverage it does not "
            "have."
        )


class TestOrphanDetectorCanActuallyAnswer:
    """The orphan detector (C-340 mechanism 2) has two silent preconditions.

    Both were live defects when it was first written, and neither would
    have reddened anything: the step would have run, exited 0, and
    reported "No orphaned branches" — while asserting nothing at all.
    Found by ``/code-review`` before merge, not by the drill that was
    supposed to have verified the detector (C-347).
    """

    def test_the_workflow_grants_pull_requests_read(self) -> None:
        """The detector is built entirely on ``gh pr list``.

        Once a ``permissions:`` block exists, every scope NOT listed is
        set to ``none`` — so omitting this one revokes it rather than
        leaving a default in place. Every ``gh pr list`` call would then
        403, and because they are written ``... 2>/dev/null) || continue``
        a 403 is indistinguishable from "no PR found": every branch is
        skipped, ``found`` stays empty, and the step reports clean on a
        daily cron, forever.

        This asserts the grant, not the calls, because the grant is the
        part no drill run under a personal token can check.
        """
        data = yaml.safe_load(HYGIENE.read_text())
        perms = data.get("permissions") or {}
        assert perms.get("pull-requests") == "read", (
            f"release-topology.yml must grant `pull-requests: read`; it "
            f"grants {perms!r}. An explicit permissions block sets every "
            f"unlisted scope to `none`, so the orphan detector's `gh pr "
            f"list` calls would 403 — swallowed by `2>/dev/null || "
            f"continue` and reported as 'No orphaned branches' (C-347)."
        )

    def test_long_lived_branches_are_fetched_before_the_detector_runs(
        self,
    ) -> None:
        """``origin/development`` must exist before the ancestry checks.

        The detector asks twice whether something is an ancestor of
        ``origin/development``. Without the fetch, that ref does not
        resolve, ``git merge-base`` exits 128 into ``2>/dev/null``, and
        the ``&&`` short-circuits — so the "already merged, skip it"
        branch does **not** fire and every remote branch falls through
        into the PR queries. Wrong order, green run: the same shape as
        the deploy-gate ordering above, for a dependency that did not
        exist when this file was written.
        """
        steps = _steps(HYGIENE, "topology")
        fetch = _index_of_run(steps, "git fetch --quiet origin main development")
        detector = _index_of_run(steps, "git ls-remote --heads origin")
        assert fetch < detector, (
            "The step fetching `main`/`development` must run BEFORE the "
            "orphan detector. The detector tests ancestry against "
            "`origin/development`; if that ref is missing, `git "
            "merge-base` exits 128, the error is swallowed, the skip "
            "does not fire, and every branch is treated as a candidate."
        )

    def test_the_branch_list_is_checked_rather_than_iterated_blind(self) -> None:
        """``for x in $(cmd)`` hides a failure of ``cmd`` completely.

        GitHub runs ``bash -e {0}`` and ``set -uo pipefail`` does not
        remove ``-e``, but a failing command substitution in a ``for``
        word list is exempt from it. Verified::

            bash -e -c 'for x in $(false | sed s/a/b/); do echo BODY; done; echo END'

        prints only ``END``. So a transient ``git ls-remote`` failure
        would give an empty loop and a confident all-clear. The list must
        be captured, its status checked, and emptiness treated as an
        error — a repository always has at least two branches.
        """
        steps = _steps(HYGIENE, "topology")
        run = steps[_index_of_run(steps, "git ls-remote --heads origin")]["run"]
        assert "for branch in $(git ls-remote" not in run, (
            "The orphan detector iterates `git ls-remote` output directly. "
            "A failure of that command is invisible there — bash's `-e` "
            "exempts command substitution in a `for` word list — so one "
            "network hiccup yields an empty loop and a green 'No orphaned "
            "branches'. Capture it, check the status, and reject empty."
        )
        # The property, not the wording. An earlier version of this
        # assertion matched the exact sentence of the log message, which
        # would redden on a reword for no behavioural reason — the same
        # "guard asserts the how, not the what" mistake C-336's second
        # addendum records.
        assert "::error::" in run and "exit 1" in run, (
            "The orphan detector must fail loudly when it cannot "
            "enumerate branches. Silently reporting clean because the "
            "listing failed is the defect the detector exists to catch."
        )

    def test_a_result_resting_on_no_observations_is_an_error(self) -> None:
        """Answering for nothing must not read as answering "all clear".

        Every per-branch check can fail — a rate limit, a 502, a branch
        deleted mid-loop — and each failure removes a branch from the
        result silently. If enough fire, the step reports a confident
        all-clear having observed nothing, which is C-347 one level down
        from the permission defect that prompted it. The step therefore
        counts what it answered for, refuses to report clean on zero, and
        qualifies a partial result rather than rounding it to success.
        """
        steps = _steps(HYGIENE, "topology")
        run = steps[_index_of_run(steps, "git ls-remote --heads origin")]["run"]
        for needle, why in [
            ("answered=", "must count the branches it actually resolved"),
            ("unanswered=", "must count the branches it could not resolve"),
            ('"$answered" -eq 0', "must detect having answered for nothing"),
        ]:
            assert needle in run, (
                f"The orphan detector no longer contains {needle!r} — it "
                f"{why}. Without the count, a run in which every branch "
                f"failed to resolve is indistinguishable from a run in "
                f"which every branch was clean (C-347)."
            )
