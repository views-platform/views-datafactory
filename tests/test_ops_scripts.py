"""Guard: operator scripts stay runnable (C-348).

These are the scripts a human is told to invoke by name from a guide.
Their failure mode is not subtle — a lost executable bit surfaces as
``Permission denied`` the moment someone runs one — but nothing else in
the suite notices that they exist at all, and that is how the coverage
was lost in the first place.

**Why this file exists separately.** The assertion below used to live in
``tests/test_git_hooks.py``, alongside tests for the pre-push hook. When
the hook was abandoned (C-340) that module was deleted with it, and this
assertion went too — silently, because deleting a test module removes
assertions nobody is thinking about. ``scripts/arm_automerge.sh`` is the
*working* half of C-340 and is deliberately kept, so its guard is kept
too, in a module named for what it actually covers rather than for what
it happened to sit next to.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GUIDE = REPO / "docs" / "guides" / "publishing_to_pypi.md"

# Scripts a guide tells an operator to run directly, by path.
OPERATOR_SCRIPTS = [
    (
        REPO / "scripts" / "arm_automerge.sh",
        "C-340 mechanism 1 — arms auto-merge and reads the method back",
    ),
]


class TestOperatorScriptsStayRunnable:
    def test_each_script_exists_and_is_executable(self) -> None:
        broken = [
            (str(path.relative_to(REPO)), why, path.is_file())
            for path, why in OPERATOR_SCRIPTS
            if not (path.is_file() and os.access(path, os.X_OK))
        ]
        assert not broken, (
            f"Operator scripts missing or not executable: {broken} "
            f"(path, purpose, exists). A mode lost to a rebase, a patch, "
            f"or a filesystem copy is invisible until someone runs the "
            f"script and gets `Permission denied`. Restore with `chmod +x`."
        )

    def test_the_guide_still_points_at_them(self) -> None:
        """A script no guide names is a script nobody runs.

        The counterweight to the test above: it must not be satisfiable
        by deleting the script, and the coverage must not drift away
        from what operators are actually told to do.
        """
        text = GUIDE.read_text()
        missing = [
            str(path.relative_to(REPO))
            for path, _why in OPERATOR_SCRIPTS
            if str(path.relative_to(REPO)) not in text
        ]
        assert not missing, (
            f"{missing} are guarded here but no longer named in "
            f"publishing_to_pypi.md. Either the guide dropped them — in "
            f"which case operators have no route to them — or they were "
            f"renamed and this list is stale."
        )
