"""Guard: every workflow that calls ``gh`` can tell it which repository.

``gh`` infers the repository from the git remote. A job with no
``actions/checkout`` has no remote, so **every** ``gh`` call fails with
``failed to run git: fatal: not a git repository`` — and because that is
a hard error rather than an empty result, it takes the whole run with it.

This is not hypothetical and it is not subtle-but-rare. ``serving-freshness.yml``
shipped that way on 2026-08-03 and **never once succeeded**: ten runs,
ten failures, until it was noticed nine days later by a code review aimed
at something else (C-351). The freshness check for served data did not
work for its entire existence.

**Why a guard rather than just the fix.** The failure is loud in the
Actions tab and silent everywhere else, which is the worst combination —
nobody opens the Actions tab on a morning when nothing seems wrong. And
the next workflow to call ``gh`` will be copied from whichever existing
one is nearest, so the property has to be checked rather than remembered.

Either answer is accepted, because both are legitimate: a job that needs
the repository checks it out, and a job that does not sets ``GH_REPO``.
What is not accepted is neither.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"

# `gh` as a command, not the letters "gh" inside a word.
_GH_CALL = re.compile(r"(?:^|[\s;&|(])gh\s+\w")


def _env_of(*scopes: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for scope in scopes:
        if scope:
            merged.update(scope.get("env") or {})
    return merged


class TestEveryGhCallKnowsItsRepository:
    def test_gh_has_a_checkout_or_gh_repo(self) -> None:
        offenders = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            data = yaml.safe_load(path.read_text())
            for job_name, job in (data.get("jobs") or {}).items():
                steps = job.get("steps") or []
                checks_out = any(
                    "actions/checkout" in (s.get("uses") or "") for s in steps
                )
                for step in steps:
                    run = step.get("run") or ""
                    if not _GH_CALL.search(run):
                        continue
                    env = _env_of(data, job, step)
                    if checks_out or "GH_REPO" in env:
                        continue
                    label = step.get("name") or step.get("id") or "<unnamed>"
                    offenders.append(f"{path.name}:{job_name}:{label}")
        assert not offenders, (
            f"These steps call `gh` in a job with neither `actions/checkout` "
            f"nor `GH_REPO` set: {offenders}. `gh` infers the repository from "
            f"the git remote, so with no checkout every call dies with "
            f"`failed to run git: fatal: not a git repository` and fails the "
            f"run. That is how serving-freshness.yml failed all ten of its "
            f"runs from the day it was added, undetected for nine days "
            f"(C-351). Either check the repo out, or set "
            f"`GH_REPO: ${{{{ github.repository }}}}`."
        )

    def test_the_guard_has_something_to_guard(self) -> None:
        """Counterweight: this must not pass by finding no `gh` at all.

        A regex that matches nothing is green forever. If the workflows
        stop calling `gh`, this guard is obsolete and should be deleted
        deliberately rather than left as decoration (C-346).
        """
        calls = sum(
            bool(_GH_CALL.search(step.get("run") or ""))
            for path in WORKFLOWS.glob("*.yml")
            for job in (yaml.safe_load(path.read_text()).get("jobs") or {}).values()
            for step in (job.get("steps") or [])
        )
        assert calls > 0, (
            "No workflow step matches the `gh` call pattern, so the guard "
            "above cannot fail. Either the regex broke or `gh` is no longer "
            "used — check which before trusting the green."
        )
