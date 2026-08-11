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
