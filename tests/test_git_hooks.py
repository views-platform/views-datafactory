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
