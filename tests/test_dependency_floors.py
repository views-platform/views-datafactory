"""Guard: no runtime dependency may sit pinned exactly at its own floor.

``uv lock`` keeps an existing pin for as long as it still satisfies the
constraint. ``>=1.0`` satisfies ``1.0.0`` forever, so a loose floor does
not merely *permit* an old version — it **freezes** one, and nothing in
the normal workflow pulls it forward. That is how ``views-frames`` stayed
at 1.0.0 from June until 2026-08-02 while three MINOR releases changed
how MAP and HDI are computed (C-337).

The audit that first cleared that floor asked *"what does this package
import?"* — four symbols, no estimators, all present at 1.0.0. Every step
of that was true and the conclusion was wrong, because a floor constrains
**the resolver**, not the import list. The lockfile, which is what
actually gets installed, was never opened.

So this file opens the lockfile. It asserts a property of the resolution,
not of the declaration:

  a package resting exactly on its floor is a package nothing has moved

That is a **symptom**, not a defect in itself. Sometimes it is entirely
correct — see ``ALLOWED_AT_FLOOR``. But it is the observable trace of the
freeze, and it is the only cheap one.

**Scope: ``[project].dependencies`` only.** The dev group and the
``[pandas]`` extra resolve through the same lockfile and can freeze the
same way, but a frozen dev tool does not reach consumers, and a frozen
extra cannot (``pandas>=2.0`` is uncapped and unfrozen). Both were checked
by hand on 2026-08-08 and neither is at its floor. Widen this if that
stops being true.

``packaging`` is imported for version comparison; hand-rolling it would
get ``2.3`` vs ``2.3.0`` wrong. It is not declared anywhere in this
project, so what guarantees it? **pytest requires it**, and nothing runs
this file except pytest — that is the whole argument, and it cannot
lapse. ``xarray`` also carries it on the runtime path. Do *not* justify
it by matplotlib: matplotlib carries ``packaging`` too, but pyproject's
own C-334 note says to drop matplotlib once views-hydranet declares it
itself, so it is the one carrier here with a scheduled end.

**Two guards were written for this file and then deleted, deliberately.**
"every declared dependency appears in the lock" and "no locked version
sits below its floor" both looked worth asserting. Both are unfailable,
and drilling them is how that was found rather than assumed:

- raising a floor above every published version makes ``uv`` refuse to
  resolve at all — pytest never starts
- hand-editing a version down in ``uv.lock`` makes ``uv`` refuse to parse
  it (*"has wheel ... with inconsistent version"*)
- an honestly-produced lock cannot be below the floor, because ``uv lock``
  resolves against ``pyproject.toml``

``uv`` enforces both properties earlier and harder than a test could. A
test that cannot fail is a green tick that checks nothing, which is the
exact defect this file was added to guard against, so it does not ship.

What ``uv`` does *not* enforce is that the **committed** lock matches the
committed ``pyproject.toml``: ``uv sync`` silently rewrites the lock, so
CI goes green on a stale one. That is real, and the instrument is
``uv lock --check`` in CI — not a test reading ``tomllib``, because by
the time pytest runs the lock has already been repaired. Registered as
**C-342**, proposed for #424; out of scope here.

C-342 also bounds what *this* file can claim. The tests below read the
committed lock, and only the way the suite is invoked (``uv run`` and
``uv sync`` both refresh first) makes that a real resolution rather than
a stale one — a property of the caller, not of this file.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

REPO = Path(__file__).resolve().parents[1]

# Packages legitimately resting on their floor, each with the reason.
#
# A name alone is not enough: an exemption whose reason has expired is a
# guard that has been silently switched off, which is the exact failure
# class this file exists to catch. ``test_allow_list_has_not_rotted``
# fails when an entry no longer applies, so the list cannot quietly grow
# stale.
#
# Emptying this dict makes that test pass unconditionally, and that is
# **correct, not a hole** — worth stating because the docstring above
# deletes two guards for exactly the "cannot fail" property. The
# difference: those two asserted things about the world that could never
# be false. This one asserts a property OF THIS DICT, and an empty dict
# has no stale entries to find. An empty allow-list is also the
# strongest possible state, because then
# ``test_no_dependency_is_pinned_at_its_floor`` — which does the real
# work — runs with no exemptions at all. Do not "fix" this by inventing
# an assertion that fires on emptiness.
ALLOWED_AT_FLOOR = {
    "views-frames": (
        "The floor IS the latest release. C-337's fix raised it to 1.10.2 "
        "on 2026-08-02 — deliberately meaning 'current' rather than 'the "
        "oldest version that happens to work'. Being at the floor here is "
        "the fix working, not the freeze. Remove this entry once "
        "views-frames publishes past 1.10.2 and the lock moves."
    ),
}


def _declared_floors() -> dict[str, str]:
    """Runtime dependency -> its ``>=`` floor, for those that declare one."""
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    floors: dict[str, str] = {}
    for dep in data["project"]["dependencies"]:
        req = Requirement(dep)
        lower = [s for s in req.specifier if s.operator == ">="]
        if lower:
            floors[canonicalize_name(req.name)] = lower[0].version
    return floors


def _locked_versions() -> dict[str, str]:
    """Every package in ``uv.lock``, canonicalised, with the chosen version."""
    lock = tomllib.loads((REPO / "uv.lock").read_text())
    return {
        canonicalize_name(pkg["name"]): pkg["version"]
        for pkg in lock["package"]
        if "version" in pkg
    }


_FIX_HINT = (
    "Run `uv lock --upgrade-package {name}`, then read what it picked and "
    "confirm the new version is intended before committing the lock."
)


class TestFloorsAreNotPins:
    def test_no_dependency_is_pinned_at_its_floor(self) -> None:
        """A package resting on its floor is a package nothing has moved."""
        locked = _locked_versions()
        allowed = {canonicalize_name(n) for n in ALLOWED_AT_FLOOR}
        stuck = {
            name: floor
            for name, floor in _declared_floors().items()
            if name not in allowed
            and name in locked
            and Version(locked[name]) == Version(floor)
        }
        assert not stuck, (
            "These runtime dependencies are locked at exactly the floor "
            f"pyproject declares: {sorted(stuck)}. "
            "Sitting on the floor is a SYMPTOM, not the bug — the bug is "
            "that `uv lock` keeps an existing pin while it still satisfies "
            "the constraint, so a loose floor freezes the version instead "
            "of merely permitting it, and no routine action moves it. "
            "Six weeks of views-frames 1.0.0 looked exactly like this "
            "(C-337). "
            + " ".join(_FIX_HINT.format(name=n) for n in sorted(stuck))
            + " If the pin is correct — typically because the floor is the "
            "latest release — add the package to ALLOWED_AT_FLOOR in this "
            "file WITH THE REASON, not just the name."
        )

    def test_allow_list_has_not_rotted(self) -> None:
        """An exemption that no longer applies is a guard switched off."""
        floors = _declared_floors()
        locked = _locked_versions()
        obsolete = []
        for raw in ALLOWED_AT_FLOOR:
            name = canonicalize_name(raw)
            if name not in floors:
                obsolete.append(f"{raw} (no longer a runtime dependency)")
            elif name not in locked:
                obsolete.append(f"{raw} (not in uv.lock)")
            elif Version(locked[name]) != Version(floors[name]):
                obsolete.append(
                    f"{raw} (floor {floors[name]}, locked {locked[name]} — "
                    f"it has moved off the floor)"
                )
        assert not obsolete, (
            f"ALLOWED_AT_FLOOR entries that no longer apply: {obsolete}. "
            "Delete them. A stale exemption exempts a package that may "
            "later freeze for a completely different reason, and it will "
            "do so silently — which is the failure class this file exists "
            "to catch."
        )
