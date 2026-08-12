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

import re
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


def _step_by_id(workflow: Path, job: str, step_id: str) -> dict[str, Any]:
    """Locate a step by its stable ``id:``.

    NOT by a substring of the body being asserted on: that makes the
    guard retarget itself if any other step ever contains the same
    command, and it couples step identity to the very text under test.
    """
    for step in _steps(workflow, job):
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"{workflow.name}:{job} has no step with id {step_id!r}")


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
    """The orphan detector's silent preconditions.

    Every assertion here was rewritten after `/code-review max` found
    that three of the four originals could not fail for the property
    they claimed: ``"answered="`` is a substring of ``"unanswered="``, so
    stripping every ``answered`` counter still matched; and a bare
    ``"::error::" in run`` was satisfied by an unrelated guard elsewhere
    in the same 130-line step, so deleting both branch-enumeration
    guards kept the suite green. A guard written against fails-green
    that itself fails green is the epic's subject, committed inside it.
    """

    def _run(self) -> str:
        """The step body with whole-line comments removed.

        Load-bearing. This step's comments quote the anti-patterns they
        warn against — ``# `for x in $(cmd)` swallows a failure`` — so a
        shape assertion run against the raw body matches the explanation
        and reddens on the *fixed* file. That is exactly how v1 of
        ``test_heartbeat_secret.py`` failed (C-336), caught here by the
        control run rather than by review.
        """
        run = _step_by_id(HYGIENE, "topology", "orphans")["run"]
        return "\n".join(
            line for line in run.splitlines() if not line.lstrip().startswith("#")
        )

    def test_the_workflow_grants_pull_requests_read(self) -> None:
        """The detector is built entirely on ``gh pr list``.

        An explicit ``permissions:`` block sets every unlisted scope to
        ``none``, so omitting this revokes it. The calls are written
        ``... 2>/dev/null) || ...``, making a 403 indistinguishable from
        "no PR found". Verified live under ``GITHUB_TOKEN`` by
        dispatching the workflow (run 31590304501), which is the only
        way to check a grant — a local drill runs as the operator.
        """
        data = yaml.safe_load(HYGIENE.read_text())
        perms = data.get("permissions") or {}
        assert perms.get("pull-requests") == "read", (
            f"release-topology.yml must grant `pull-requests: read`; it "
            f"grants {perms!r}. Without it every `gh pr list` 403s, is "
            f"swallowed, and the step reports clean forever (C-347)."
        )

    def test_the_branch_list_is_not_iterated_blind(self) -> None:
        """``for x in $(cmd)`` hides a failure of ``cmd`` completely.

        GitHub runs ``bash -e {0}``; ``set -uo pipefail`` does not remove
        ``-e``; and a failing command substitution in a ``for`` word list
        is exempt from it. So a transient ``ls-remote`` failure gives an
        empty loop and a confident all-clear.

        Matched on the *shape* rather than on the loop variable's name,
        which the first version keyed on and which a rename defeated.
        """
        assert not re.search(r"for\s+\w+\s+in\s+\$\(", self._run()), (
            "The orphan detector iterates a command substitution "
            "directly. A failure of that command is invisible there, so "
            "one network hiccup yields an empty loop and a green 'No "
            "orphaned branches'. Capture it, check the status, reject "
            "empty (C-347)."
        )

    def test_failing_to_enumerate_branches_is_loud(self) -> None:
        """Both enumeration guards must survive, individually.

        The first version asserted ``"::error::" in run and "exit 1" in
        run`` against the whole step — satisfied on their own by the
        zero-observation guard a hundred lines below, so deleting BOTH
        enumeration guards left it green. Each is now anchored to the
        condition it guards.
        """
        run = self._run()
        pattern = r"git ls-remote[^\n]*\n(?:[^\n]*\n)?\s*echo \"::error::"
        assert re.search(pattern, run), (
            "The `git ls-remote` failure path no longer raises an error. "
            "Reporting clean because the branch listing failed is exactly "
            "the defect the detector exists to catch."
        )
        assert re.search(r'\[ -n "\$branches" \]', run), (
            "The empty-branch-list guard is gone. `ls-remote` succeeding "
            "and returning nothing is not the same as 'no branches' — a "
            "repository always has at least main and development."
        )

    def test_answered_and_unanswered_are_counted_separately(self) -> None:
        """The counting the zero-observation rule rests on.

        ``"answered="`` is a SUBSTRING of ``"unanswered="``, so the first
        version of this test passed with every ``answered`` counter
        deleted. The lookbehind is the whole point.
        """
        run = self._run()
        assert re.search(r"(?<!un)answered=\$\(\(answered \+ 1\)\)", run), (
            "No `answered=$((answered + 1))` increment remains. Without "
            "it `answered` is always 0 and the zero-observation guard "
            "below fires on every run, or — if that guard is also gone — "
            "a scan that answered for nothing reports clean (C-347)."
        )
        assert "unanswered=$((unanswered + 1))" in run, (
            "No `unanswered` increment remains, so a branch the detector "
            "could not check is indistinguishable from one it checked "
            "and found clean."
        )
        assert re.search(r'\[ "\$answered" -eq 0 \]', run), (
            "The zero-observation guard is gone. A clean report resting "
            "on no observations is the defect itself, not a degraded "
            "mode of it (C-347)."
        )

    def test_a_partial_scan_does_not_report_a_clean_result(self) -> None:
        """`orphans=false` is what closes the tracking issue.

        If a scan that could not reach some branches wrote `false`, the
        close step would close a live orphan issue on the strength of a
        scan that skipped the very branch it was about. A third value is
        the point: `partial` neither opens nor closes.
        """
        run = self._run()
        assert "orphans=partial" in run, (
            "The detector no longer distinguishes a partial scan from a "
            "clean one. `orphans=false` drives the issue-close step, so a "
            "degraded scan writing `false` closes a live orphan issue "
            "(C-347)."
        )
        # And a finding must survive a degraded scan rather than being
        # rounded down to "partial".
        assert run.index('orphans=true') < run.index('orphans=partial'), (
            "The `found` branch must be tested BEFORE the partial branch, "
            "or a real orphan discovered during a degraded scan is "
            "reported as merely 'partial' and never opens an issue."
        )
