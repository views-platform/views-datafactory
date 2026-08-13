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

**A package can resolve MORE THAN ONCE.** Since the floor dropped to 3.11
(#443) the lock forks: ``tifffile`` and ``imagecodecs`` each have two
entries, an older one for 3.11 and the current one for >=3.12, chosen by
marker. So the floor is compared against **every** resolution, and the
messages print all of them.

That collapse used to be a real hole here. ``_locked_versions`` was a dict
comprehension keyed by name, which silently kept whichever entry ``uv``
serialised last and reported success about a version it never read — in
the file whose entire subject is mechanisms that fail green. It was raised
during ``/code-review`` on #430, scored 25, and **correctly refuted**: see
``register_changelog.md``, *"a dict-collision path that this project's
single ``requires-python`` and marker-free dependencies cannot reach."*
#443 deleted that premise. **A refutation is only as durable as its
premise, and nothing was watching the premise.**

**Strict, not lenient.** A package is flagged when *any* resolution equals
the floor, not only when the highest does. Lenient (``max == floor``) is
quieter and structurally blind to one fork freezing while its sibling
moves — which is exactly what ``uv lock``'s keep-the-existing-pin
behaviour produces, per fork. Under lenient, a new fork appearing would
silently widen what this guard tolerates, with no diff to review. The
cost of strict is an occasional flag on a legitimate upstream ceiling, and
that is not a cost: ``ALLOWED_AT_FLOOR`` already demands a written reason
and ``test_allow_list_has_not_rotted`` already expires it.

**Scope: ``[project].dependencies`` only.** The dev group and the
``[pandas]`` extra resolve through the same lockfile and can freeze the
same way, but a frozen dev tool does not reach consumers, and a frozen
extra cannot (``pandas>=2.0`` is uncapped and unfrozen). Re-checked by
hand on 2026-08-13 against the **forked** lock — the earlier check was run
before the fork existed, so it was a claim about a different world. Both
still clear. Widen this if that stops being true.

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


def _parse_locked_versions(lock_text: str) -> dict[str, list[Version]]:
    """Canonical package name -> **every** version the lock resolves for it.

    A list, and the list is the entire point: ``uv`` writes one
    ``[[package]]`` block per marker environment, so a forked package
    appears more than once. Taking a dict comprehension here discards all
    but one and reports on a version nobody read.

    Split from :func:`_locked_versions` so the parser has a seam and can
    be tested against a fixture rather than against whatever ``uv.lock``
    happens to contain today — see ``TestTheLockParserSeesEveryFork``.
    """
    lock = tomllib.loads(lock_text)
    versions: dict[str, list[Version]] = {}
    for pkg in lock["package"]:
        if "version" in pkg:
            key = canonicalize_name(pkg["name"])
            versions.setdefault(key, []).append(Version(pkg["version"]))
    return versions


def _locked_versions() -> dict[str, list[Version]]:
    return _parse_locked_versions((REPO / "uv.lock").read_text())


def _show(versions: list[Version]) -> str:
    return ", ".join(str(v) for v in sorted(versions))


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
            name: f"floor {floor}, resolved {_show(locked[name])}"
            for name, floor in _declared_floors().items()
            if name not in allowed
            and name in locked
            and any(v == Version(floor) for v in locked[name])
        }
        assert not stuck, (
            "These runtime dependencies have a resolution sitting at exactly "
            f"the floor pyproject declares: {stuck}. "
            "Sitting on the floor is a SYMPTOM, not the bug — the bug is "
            "that `uv lock` keeps an existing pin while it still satisfies "
            "the constraint, so a loose floor freezes the version instead "
            "of merely permitting it, and no routine action moves it. "
            "Six weeks of views-frames 1.0.0 looked exactly like this "
            "(C-337). Every resolution is listed above BECAUSE that is the "
            "judgement you have to make: a package can be at its floor in "
            "one marker environment and current in another, which is an "
            "upstream ceiling and fine, or frozen in all of them, which is "
            "not. "
            + " ".join(_FIX_HINT.format(name=n) for n in sorted(stuck))
            + " If the pin is correct — typically because the floor is the "
            "latest release, or because upstream dropped the interpreter "
            "that fork serves — add the package to ALLOWED_AT_FLOOR in this "
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
            elif not any(v == Version(floors[name]) for v in locked[name]):
                obsolete.append(
                    f"{raw} (floor {floors[name]}, resolved "
                    f"{_show(locked[name])} — no resolution is on the floor "
                    f"any more)"
                )
        assert not obsolete, (
            f"ALLOWED_AT_FLOOR entries that no longer apply: {obsolete}. "
            "Delete them. A stale exemption exempts a package that may "
            "later freeze for a completely different reason, and it will "
            "do so silently — which is the failure class this file exists "
            "to catch."
        )


class TestTheLockParserSeesEveryFork:
    """The parser, drilled against a fixture rather than the real lock.

    Deliberately NOT written as "the number of parsed versions equals the
    number of `[[package]]` blocks in uv.lock" — that assertion is
    unfailable whenever the lock happens to have no duplicates, which is
    the green-tick-that-checks-nothing standard this file deletes other
    guards for. A fixture with a known fork can always fail.
    """

    _FORKED = """
version = 1

[[package]]
name = "tifffile"
version = "2026.3.3"

[[package]]
name = "tifffile"
version = "2026.5.15"

[[package]]
name = "Some_Other-Pkg"
version = "1.2.3"
"""

    def test_both_entries_for_one_name_are_returned(self) -> None:
        parsed = _parse_locked_versions(self._FORKED)
        assert parsed["tifffile"] == [
            Version("2026.3.3"),
            Version("2026.5.15"),
        ], (
            "The parser dropped a fork. A dict keyed by package name keeps "
            "only the last entry, so the guard would compare the floor "
            "against a version it never read and report success. That is "
            "the exact collapse #443 exposed when the 3.11 floor made "
            "uv.lock multi-version."
        )

    def test_names_are_canonicalised(self) -> None:
        parsed = _parse_locked_versions(self._FORKED)
        assert "some-other-pkg" in parsed, sorted(parsed)
