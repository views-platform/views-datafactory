"""Guard: the pre-push hook stays installable and stays fail-open.

The hook itself is the machinery for C-340 mechanism 2 — it runs on every
push and cannot be forgotten. What a test can add is narrow but real:

**It must remain executable.** Git silently ignores a hook without the
executable bit. No error, no warning — the protection just stops, and the
next push to a merged branch orphans a commit exactly as #416's did. A
mode lost to a rebase, a patch, or a filesystem copy is invisible.

**It must remain fail-open.** Every path where the hook cannot answer —
no ``gh``, no auth, no network — has to allow the push. A hook that
blocks work when it does not know gets uninstalled within a day, and
then it protects nothing at all. This asserts the escape hatches are
still present rather than that they still work; the behaviour is drilled
separately, in the PR.

**The install step must stay documented.** ``core.hooksPath`` is per-clone
config that git does not version, so a hook nobody installs is a file
nobody runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "scripts" / "git-hooks" / "pre-push"
ARM = REPO / "scripts" / "arm_automerge.sh"
GUIDE = REPO / "docs" / "guides" / "publishing_to_pypi.md"


class TestHookStaysUsable:
    def test_hook_exists_and_is_executable(self) -> None:
        assert HOOK.is_file(), f"{HOOK} is missing — C-340 mechanism 2 is unguarded"
        assert os.access(HOOK, os.X_OK), (
            f"{HOOK} has lost its executable bit. Git ignores a non-executable "
            f"hook SILENTLY — no error, no warning, the protection simply "
            f"stops. Restore with `chmod +x`."
        )

    def test_arm_helper_exists_and_is_executable(self) -> None:
        assert ARM.is_file(), f"{ARM} is missing"
        assert os.access(ARM, os.X_OK), f"{ARM} has lost its executable bit"

    def test_hook_still_fails_open(self) -> None:
        """Every 'cannot answer' path must allow the push."""
        text = HOOK.read_text()
        for needle, why in [
            ("command -v gh", "must check gh exists before using it"),
            ("gh not installed", "must say why it is allowing when gh is absent"),
            ("could not answer", "must say why it is allowing when gh cannot auth"),
            ("--no-verify", "must tell the operator the escape hatch"),
        ]:
            assert needle in text, (
                f"pre-push hook no longer contains {needle!r} — it {why}. "
                f"A hook that blocks work when it cannot answer is worse than "
                f"the problem it solves; it gets uninstalled, and then it "
                f"guards nothing (C-320's lesson applied to a hook)."
            )

    def test_install_step_is_documented(self) -> None:
        assert "core.hooksPath" in GUIDE.read_text(), (
            "publishing_to_pypi.md no longer documents "
            "`git config core.hooksPath scripts/git-hooks`. That setting is "
            "per-clone and git does not version it, so an undocumented hook "
            "is a file nobody installs."
        )


BASH = shutil.which("bash") or "/bin/bash"


def _sandbox_without_gh(tmp_path: Path) -> str:
    """A PATH holding everything the hook needs EXCEPT ``gh``.

    Not simply an empty PATH: the hook also runs ``git`` and ``sed``, so
    blanking PATH would exercise a different failure than the one under
    test. The first version of this helper set ``PATH=/nonexistent-bin``
    and hid ``bash`` from the test runner itself — the harness broke, not
    the hook.
    """
    binder = tmp_path / "bin"
    binder.mkdir(exist_ok=True)
    for tool in ("bash", "git", "sed", "cat", "tr", "cut", "printf"):
        found = shutil.which(tool)
        if found:
            link = binder / tool
            if not link.exists():
                link.symlink_to(found)
    assert shutil.which("gh", path=str(binder)) is None, (
        "sandbox still exposes gh — the drill would test nothing"
    )
    return str(binder)


def _run_hook(stdin: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke the hook the way git does: refs on stdin, remote in argv."""
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [BASH, str(HOOK), "origin", "https://example.invalid/repo.git"],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO,
    )


ZERO = "0" * 40


class TestHookReadsWhatGitActuallySends:
    """Behavioural, because the substring checks above caught neither bug.

    Review of #437 found two defects that every text assertion in this
    file passed straight over:

    1. the hook read the branch from ``git rev-parse HEAD`` instead of
       from stdin, so ``git push origin feature-a:feature-a`` while
       ``main`` was checked out was never checked at all — silently
       allowing the push the hook exists to refuse;
    2. it matched on branch *name*, so a fresh branch reusing a name
       (this repo has several) was permanently refused.

    A guard that only greps its own source proves the source contains
    words. These run it.
    """

    def test_a_delete_push_is_allowed(self) -> None:
        """local sha of all zeros means "delete" — nothing is being added."""
        r = _run_hook(f"refs/heads/x {ZERO} refs/heads/x abc123\n")
        assert r.returncode == 0, (
            f"deleting a remote branch must not be refused; got "
            f"{r.returncode}\n{r.stderr}"
        )

    def test_a_tag_push_is_allowed(self) -> None:
        r = _run_hook(f"refs/tags/v9.9.9 abc123 refs/tags/v9.9.9 {ZERO}\n")
        assert r.returncode == 0, (
            f"tag pushes have no PR and must not be refused; got "
            f"{r.returncode}\n{r.stderr}"
        )

    def test_long_lived_branches_are_allowed(self) -> None:
        for branch in ("main", "development"):
            r = _run_hook(
                f"refs/heads/{branch} abc123 refs/heads/{branch} {ZERO}\n"
            )
            assert r.returncode == 0, (
                f"{branch} is pushed to constantly and has no PR of its "
                f"own; got {r.returncode}\n{r.stderr}"
            )

    def test_empty_stdin_is_allowed(self) -> None:
        assert _run_hook("").returncode == 0

    def test_creating_a_branch_is_allowed_even_if_the_name_was_used_before(
        self,
    ) -> None:
        """The reused-name case, which two earlier versions got wrong.

        ``remote_sha`` of all zeros means the remote ref does not exist —
        the branch is being created. There is nothing on the remote to add
        to, so this cannot be C-340 mechanism 2 whatever the name.

        This repo really does reuse names: ``docs/roadmap-plan-v11``
        spans PRs #50-54 and ``feat/acled-phase2`` spans #35-36. v1 of
        this hook refused all of them permanently. v2 refused them too,
        for a subtler reason — it asked whether the merged head was an
        *ancestor*, and a merge-commit merge puts that head into the base
        branch's history forever, so it is an ancestor of every branch cut
        from it afterwards.

        Short-circuits before ``gh`` is consulted, so this asserts the
        real decision rather than an offline fallback.
        """
        r = _run_hook(
            f"refs/heads/docs/roadmap-plan-v11 abc123 "
            f"refs/heads/docs/roadmap-plan-v11 {ZERO}\n"
        )
        assert r.returncode == 0, (
            f"creating a branch must never be refused, however many merged "
            f"PRs once used that name; got {r.returncode}\n{r.stderr}"
        )
        assert not r.stderr.strip(), (
            f"should short-circuit silently before consulting gh; "
            f"stderr was {r.stderr!r}"
        )

    def test_it_allows_when_gh_is_absent(self, tmp_path: Path) -> None:
        """The fail-open path, executed rather than grepped."""
        r = _run_hook(
            f"refs/heads/anything abc123 refs/heads/anything {ZERO}\n",
            path=_sandbox_without_gh(tmp_path),
        )
        assert r.returncode == 0, (
            f"must allow when gh cannot be found; got {r.returncode}"
        )
        assert "gh not installed" in r.stderr, (
            f"must say WHY it allowed; stderr was {r.stderr!r}"
        )

    def test_it_reads_the_ref_from_stdin_not_from_head(
        self, tmp_path: Path
    ) -> None:
        """The defect that made the hook check the wrong branch entirely.

        With ``gh`` unavailable every branch is allowed, so this cannot
        assert a refusal. What it can assert is that the hook *consulted
        the ref it was handed* rather than the checked-out branch: given
        a non-long-lived ref on stdin it reaches the gh lookup and says
        so, whereas the old HEAD-based version would have taken the
        ``main``/``development`` fast path and stayed silent.
        """
        r = _run_hook(
            f"refs/heads/some-feature abc123 refs/heads/some-feature {ZERO}\n",
            path=_sandbox_without_gh(tmp_path),
        )
        assert "gh not installed" in r.stderr, (
            "the hook did not reach the gh lookup for a ref given on "
            "stdin — it is not reading stdin. That is the defect where "
            "`git push origin feature-a:feature-a` from `main` went "
            "entirely unchecked."
        )
