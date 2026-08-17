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
    the ref-creation lines while "tidying" and the gates go on
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
WORKFLOWS = REPO / ".github" / "workflows"


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
        refs = _index_of_run(steps, "update-ref refs/heads/main")
        gates = _index_of_run(steps, "test_falsification_deploy_v160")
        assert refs < gates, (
            "The step creating local `main`/`development` refs must run "
            "before the deploy gates. `actions/checkout` leaves one local "
            "branch, so without those refs `git merge-base --is-ancestor "
            "main development` exits 128 and the topology gates SKIP "
            "themselves — reporting success while asserting nothing, which "
            "is C-341 exactly."
        )

    def test_the_ref_step_does_not_force_update_a_checked_out_branch(
        self,
    ) -> None:
        """`git branch -f <current>` is refused, and killed this job for 2 days.

        This workflow triggers on `release` and `schedule`, both of which
        check out the DEFAULT branch — so HEAD is on `main`. The original
        form, `git branch -f main origin/main`, dies with "fatal: Cannot
        force update the current branch", and because it is step 3 of 13,
        *every* later step was skipped: the gates, and the step that closes
        the tracking issue. Reproduced locally rather than inferred.

        The test above only ever asserted the step EXISTS and comes first.
        It was true and green throughout. This one asserts the step can
        actually run — which is the difference #450 was about.
        """
        steps = _steps(HYGIENE, "topology")
        refs = steps[_index_of_run(steps, "update-ref refs/heads/main")]
        run = refs.get("run") or ""
        for branch in ("main", "development"):
            assert f"git branch -f {branch}" not in run, (
                f"The ref step uses `git branch -f {branch}`. This workflow "
                f"runs on the default branch, so git refuses to force-update "
                f"whichever branch is checked out and the whole job dies "
                f"before the gates. Use `git update-ref refs/heads/{branch} "
                f"origin/{branch}`, which writes the ref regardless of what "
                f"is checked out. See #450."
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


def _floor() -> str:
    """The `>=` floor from requires-python — the single source of truth."""
    import tomllib

    requires = tomllib.loads((REPO / "pyproject.toml").read_text())["project"][
        "requires-python"
    ]
    assert requires.startswith(">="), (
        f"requires-python is {requires!r}; these guards assume a `>=` floor. "
        f"If the form changed, update them rather than deleting them."
    )
    return requires.removeprefix(">=").split(",")[0].strip()


def _python_pins(workflow: Path) -> dict[str, str]:
    """job -> the `python-version` it hands setup-python, where it sets one.

    Any step whose `uses` mentions setup-python OR setup-uv counts: setup-uv
    also accepts a `python-version` input, and publish_package.yml uses that
    form. Reading only setup-python would leave the release build's pin
    unguarded.
    """
    data = yaml.safe_load(workflow.read_text())
    pins: dict[str, str] = {}
    for job, spec in (data.get("jobs") or {}).items():
        for step in spec.get("steps") or []:
            uses = step.get("uses") or ""
            if "actions/setup-python" in uses or "setup-uv" in uses:
                pin = (step.get("with") or {}).get("python-version")
                if pin is not None:
                    pins[job] = str(pin)
    return pins


class TestCiPinsTrackTheDeclaredFloor:
    """Every workflow pin must equal the floor pyproject declares.

    **What this does NOT cover, stated because the first draft of this
    docstring overclaimed it** (caught in review on #444): the drift that
    actually happened between 2026-05-18 and 2026-08-13 was
    `hetzner_deployment_guide.md` saying "Install Python 3.10+" while
    pyproject said `>=3.12` — an instruction producing an environment where
    the package could not be installed. This test would have been **green**
    for that entire window, because CI's pins and pyproject agreed with each
    other; only the prose disagreed. Verified against `12d5afa`.

    So: this binds workflow pins to `requires-python`. Nothing yet binds
    prose to either. Do not cite this test as covering the guide.
    """

    # Jobs allowed to differ, each because it is deliberately NOT the floor.
    # An allow-list rather than a derived rule: deriving ("every job with a
    # setup-python step") would silently start excusing any future job that
    # drifts, which is the failure this guard exists to prevent.
    NOT_THE_FLOOR = {"test-py313"}

    def test_every_workflow_pin_equals_the_declared_floor(self) -> None:
        wrong = {}
        for wf in sorted(WORKFLOWS.glob("*.yml")):
            for job, pin in _python_pins(wf).items():
                if job not in self.NOT_THE_FLOOR and pin != _floor():
                    wrong[f"{wf.name}:{job}"] = pin
        assert not wrong, (
            f"pyproject declares a floor of {_floor()}, but these workflow "
            f"jobs pin something else: {wrong}. CI must exercise the weakest "
            f"supported configuration — it is the one no developer runs "
            f"locally. Change the pins, or change the floor deliberately and "
            f"change them together.\n\n"
            f"Scanning ALL workflows, not just ci.yml, because "
            f"publish_package.yml builds the artefact that actually reaches "
            f"consumers: a floor raised in pyproject and not there would "
            f"build the release on an interpreter below requires-python."
        )

    def test_hardcoded_python_flags_match_the_floor(self) -> None:
        """`uv run --python X` is a pin too, and setup-python cannot see it.

        Scans executable lines only. Comments are stripped first, and jobs in
        ``NOT_THE_FLOOR`` are exempt — both because the first version of this
        guard reddened on a comment mentioning an old version, and on the one
        job whose whole purpose is running off the floor. A guard that goes
        red for reasons unrelated to what it asserts stops being read, which
        is C-320; it is not much use adding one of those to a change that
        cites C-320 three times.
        """
        pattern = re.compile(r"--python\s+(\d+\.\d+)")
        wrong = []
        for wf in sorted(WORKFLOWS.glob("*.yml")):
            for job, spec in (
                yaml.safe_load(wf.read_text()).get("jobs") or {}
            ).items():
                if job in self.NOT_THE_FLOOR:
                    continue
                for step in spec.get("steps") or []:
                    run = step.get("run") or ""
                    code = "\n".join(
                        ln for ln in run.splitlines()
                        if not ln.lstrip().startswith("#")
                    )
                    for ver in set(pattern.findall(code)):
                        if ver != _floor():
                            wrong.append(f"{wf.name}:{job}: --python {ver}")
        assert not wrong, (
            f"Workflow steps pin an interpreter on the command line that is "
            f"not the declared floor ({_floor()}): {wrong}. "
            f"publish_package.yml's version guards use this form, so they are "
            f"invisible to the setup-python check above — which is exactly how "
            f"a pin drifts unnoticed."
        )


class TestSomethingTestsANonFloorInterpreter:
    """The floor is not the only supported version, so it cannot be the only tested one.

    Since #443 the lockfile forks: 3.11 resolves an older tifffile and
    imagecodecs than >=3.12 does, so the required `test` job decodes
    rasters with a different codec build than the server. `test-py313`
    is the only thing covering the production line. Delete it while
    tidying and this test is what notices.

    Asserted as a property ("some job runs pytest on a non-floor
    interpreter") rather than by name, so renaming the job is fine and
    removing the coverage is not.
    """

    def test_a_job_runs_pytest_on_something_other_than_the_floor(self) -> None:
        floor = _floor()
        jobs = yaml.safe_load(CI.read_text())["jobs"]

        covering = [
            name
            for name in jobs
            if (pin := _python_pins(CI).get(name)) is not None
            and pin != floor
            # A BARE `uv run pytest` — the full suite. `import-enforcement`
            # runs `pytest tests/test_import_enforcement.py -x -q`, so a
            # substring match on "pytest" would let it satisfy this guard if
            # its pin ever differed from the floor, and `test-py313` could
            # then be deleted with the test still green.
            and any(
                re.search(
                    r"uv run (--frozen )?pytest\s*$",
                    (s.get("run") or "").strip(),
                )
                for s in _steps(CI, name)
            )
        ]
        assert covering, (
            f"No ci.yml job runs pytest on an interpreter other than the "
            f"declared floor ({floor}). The floor is not the only supported "
            f"version — classifiers claim more — and since #443 the lock "
            f"resolves a DIFFERENT raster stack above 3.11, so testing only "
            f"the floor leaves the version the server actually runs "
            f"unexercised. Restore a job like `test-py313`. Do NOT solve "
            f"this with strategy.matrix: it renames the required `test` "
            f"check and every PR then blocks forever."
        )
