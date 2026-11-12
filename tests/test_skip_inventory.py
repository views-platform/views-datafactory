"""Coverage must not be able to disappear quietly.

Story 7 of epic #547 (issue #554). The delivery defect shipped because a
correct test stopped running and nothing said so. Forty-seven spatial
tests passed, one skipped, and in every report anyone read the skip was
indistinguishable from a pass.

This module is a **ratchet on the number of places a test can decline to
run.** It derives the live set of skip sites with ``ast`` and asserts it
against the committed inventory below. A new skip goes red and names the
file; removing one is free. The remedy for a red is to add the site to
``_INVENTORY`` with its reason, which puts the justification in the diff
rather than in someone's head.

**Why an inventory and not a count of what actually skipped.** The
obvious design -- assert the number of skipped tests in a run -- cannot
work here. How many tests skip depends on the environment: this machine
has ``data/``, a CI runner does not, and
``test_falsification_deploy_v160`` skips or does not depending on
whether ``HEAD`` sits on a ``v*`` tag, which flips on every release
commit. Both `development` and `main` require this job and set
``enforce_admins``, so a guard that flutters would wedge the branch
closed for reasons unrelated to the code. That is the failure recorded
in the register as the permanently-red-CI concern, and it is worse than
the gap it would close. An inventory of *declared* skip sites is a
property of the source, so it is identical on every machine.

**What this does not catch**, stated rather than discovered later:

1. An existing skip that begins firing where it previously did not --
   a runner losing ``data/``, a fixture quietly disappearing. The count
   of sites is unchanged; only the count of *skips* moves. The
   deselection and withholding summary in ``tests/conftest.py`` is what
   makes that visible to a reader, and nothing asserts it.
2. A skip swapped for a different skip inside the same file. The count
   is unchanged, so no count-based scheme can see it, including an
   exact one.
3. ``@pytest.mark.xfail``. An xfail declares an expectation of failure
   and is reported as such; it is not coverage withheld.

Measured 2026-11-12: **61 sites across 22 files.** Issue #554 recorded
62 before #550, and the one that went is exactly the module-level
``skipif`` #550 deleted from the spatial delivery guards.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent

#: Every file that may decline to run a test, and how many places in it
#: may do so. A file absent from this mapping may have **no** skip
#: sites. Counts are ceilings: they may fall freely, and a rise is the
#: thing this module exists to stop.
#:
#: Dispositions, and the reason each group is still here, are in
#: ``reports/test_skip_catalogue.md``. Keep that document and this
#: mapping in step -- the catalogue is the prose, this is the ratchet.
_INVENTORY: dict[str, int] = {
    # Group A -- real GAUL geography. Reviewed under #550: these assert
    # facts about the shipped GAUL release, so synthetic crosswalks
    # cannot stand in for them.
    "test_falsification_adr043.py": 3,
    "test_falsification_round2.py": 1,
    "test_falsification_shdi_ordering.py": 1,
    "test_hierarchical_reconciliation.py": 1,
    # Group B -- the consolidated UCDP store, plus the real Tigray event.
    "test_adr049_profile_contract.py": 2,
    "test_adr053_production_profile.py": 3,
    # Groups C and D -- pipeline artefacts on disk: assembled grid,
    # zarr store, built viewpoint, compiled grid.
    "test_consumer_parity.py": 4,
    "test_falsification_deploy_readiness.py": 2,
    "test_falsification_executability.py": 4,
    "test_falsification_ghsbuilts_visual_audit.py": 2,
    "test_falsification_staleness.py": 6,
    "test_model_parity.py": 5,
    "test_pipeline_consistency.py": 7,
    # Group E -- a sibling repository checkout.
    "test_structural_invariants.py": 5,
    "test_falsification_shining_codex.py": 2,
    "test_falsification_viewser_replacement.py": 2,
    # Group F -- git refs, a deep checkout, or an authenticated gh CLI.
    "test_falsification_deploy_v160.py": 5,
    "test_falsification_deploy_v160_r2.py": 2,
    # Group G -- the live server.
    "test_falsification_preflight_netrc.py": 1,
    # Group I -- a committed repository file. These should never skip,
    # and are the three the catalogue marks as wrong rather than
    # environmental.
    "test_falsification_ghspop_deploy.py": 1,
    "test_falsification_ghspop_memory.py": 1,
    # Group J -- a source fixture that is not committed.
    "test_acled_harvester.py": 1,
}

#: Guard against the walker silently matching nothing -- an inventory
#: test that scanned zero files would pass on an empty repository.
_MIN_FILES_SCANNED = 60


def _skip_sites(path: Path) -> list[tuple[int, str]]:
    """Every place in one test module that can decline to run.

    Three forms, all three real in this suite:

    - ``@pytest.mark.skipif(...)`` / ``@pytest.mark.skip(...)`` on a
      function or a class
    - ``pytest.skip(...)`` called inside a test or a fixture
    - a module-level ``pytestmark`` carrying either

    Parsed rather than grepped. A regex over this suite matched inside
    unrelated calls and stopped at the first closing paren of a nested
    one; the same mistake in a call-site scan during #552 produced nine
    false positives before it was rewritten with ``ast``.
    """
    tree = ast.parse(path.read_text())
    sites: list[tuple[int, str]] = []

    def _is_skip_marker(node: ast.expr) -> bool:
        target = node.func if isinstance(node, ast.Call) else node
        if not isinstance(target, ast.Attribute | ast.Name):
            return False
        return ast.unparse(target).endswith(
            ("pytest.mark.skipif", "pytest.mark.skip"),
        )

    for node in ast.walk(tree):
        for decorator in getattr(node, "decorator_list", []):
            if _is_skip_marker(decorator):
                sites.append((decorator.lineno, "decorator"))
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute | ast.Name) and (
                ast.unparse(func) == "pytest.skip"
            ):
                sites.append((node.lineno, "call"))

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "pytestmark" for t in node.targets
        ):
            source = ast.unparse(node.value)
            if "skipif" in source or "mark.skip" in source:
                sites.append((node.lineno, "module"))

    return sites


def _live_inventory() -> dict[str, list[tuple[int, str]]]:
    """Every test module with at least one skip site."""
    found: dict[str, list[tuple[int, str]]] = {}
    scanned = 0
    for path in sorted(_TESTS_DIR.glob("test_*.py")):
        scanned += 1
        sites = _skip_sites(path)
        if sites:
            found[path.name] = sites
    assert scanned >= _MIN_FILES_SCANNED, (
        f"the walker scanned only {scanned} test modules, which means it "
        f"is pointed at the wrong directory -- every assertion below "
        f"would pass by looking at nothing"
    )
    return found


class TestSkipInventoryGreen:
    """The declared inventory and the live suite must agree."""

    def test_the_walker_finds_the_sites_it_is_supposed_to_find(
        self,
    ) -> None:
        """Premise guard, before any assertion that could pass on zero.

        If this module's own walker found nothing, every ratchet below
        would be vacuous. It asserts against a lower bound rather than
        the exact count so that removing a skip does not fail it.
        """
        live = _live_inventory()
        total = sum(len(v) for v in live.values())
        assert total >= 40, (
            f"found only {total} skip sites across {len(live)} files; "
            f"61 were measured on 2026-11-12, so the walker is broken "
            f"rather than the suite being clean"
        )

    def test_no_file_declines_to_run_more_often_than_declared(
        self,
    ) -> None:
        """The ratchet. A rise is red; a fall is free."""
        live = _live_inventory()
        risen = {
            name: (len(sites), _INVENTORY[name])
            for name, sites in live.items()
            if name in _INVENTORY and len(sites) > _INVENTORY[name]
        }
        assert not risen, (
            "a test module gained a way to decline to run:\n"
            + "\n".join(
                f"  {name}: {now} sites, {declared} declared"
                for name, (now, declared) in sorted(risen.items())
            )
            + "\n\nIf the new skip is correct, add it to _INVENTORY in "
            "tests/test_skip_inventory.py and give its reason in "
            "reports/test_skip_catalogue.md. The number is meant to be "
            "edited deliberately -- that is the whole mechanism."
        )

    def test_no_undeclared_file_declines_to_run(self) -> None:
        """A file absent from the inventory may have no skip sites."""
        live = _live_inventory()
        undeclared = {
            name: [ln for ln, _ in sites]
            for name, sites in live.items()
            if name not in _INVENTORY
        }
        assert not undeclared, (
            "a test module not in the inventory now declines to run:\n"
            + "\n".join(
                f"  {name}: line(s) {lines}"
                for name, lines in sorted(undeclared.items())
            )
            + "\n\nAdd it to _INVENTORY with its reason, or remove the "
            "skip. A skip nobody declared is the condition this module "
            "exists to prevent."
        )


class TestSkipInventoryRed:
    """The inventory itself must not rot into a rubber stamp."""

    def test_the_inventory_names_no_file_that_no_longer_exists(
        self,
    ) -> None:
        """A stale entry is slack the ratchet would never notice.

        An inventory line for a deleted module silently permits nothing,
        which is harmless, but it also makes the document describing the
        suite wrong. Cheap to assert, so asserted.
        """
        missing = sorted(
            name for name in _INVENTORY
            if not (_TESTS_DIR / name).exists()
        )
        assert not missing, (
            f"the inventory names test modules that do not exist: "
            f"{missing}"
        )

    def test_the_inventory_grants_no_allowance_to_a_clean_file(
        self,
    ) -> None:
        """An entry for a file with no skip sites is dead slack.

        This is the way the ratchet would decay: someone removes the
        last skip from a module, leaves its allowance of 3 behind, and
        three new skips can then land silently. Caught here instead.
        """
        live = _live_inventory()
        dead = sorted(name for name in _INVENTORY if name not in live)
        assert not dead, (
            f"the inventory still allows skips in modules that have "
            f"none: {dead}. Remove the entries -- an unused allowance "
            f"is a hole the ratchet cannot see through."
        )

    @pytest.mark.parametrize(
        "name", sorted(_INVENTORY), ids=sorted(_INVENTORY),
    )
    def test_each_declared_allowance_is_fully_used(
        self, name: str,
    ) -> None:
        """Exact, per file, so slack cannot accumulate anywhere.

        The ceiling in ``test_no_file_declines_to_run_more_often_than_
        declared`` is what keeps a release commit from turning this
        red. This test is the other half: it requires the declared
        number to be the true number *today*, so the slack a ceiling
        would otherwise allow is zero. Removing a skip therefore fails
        here -- deliberately. Removing coverage-withholding is good news
        and it still has to be written down.
        """
        live = _live_inventory()
        sites = live.get(name, [])
        assert len(sites) == _INVENTORY[name], (
            f"{name} declares {_INVENTORY[name]} skip sites and has "
            f"{len(sites)} at line(s) {[ln for ln, _ in sites]}. If a "
            f"skip was removed, lower the number here and strike the "
            f"row in reports/test_skip_catalogue.md."
        )
