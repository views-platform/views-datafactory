"""Guard: the declared views-frames floor must stay above the estimator changes.

A dependency floor constrains **the resolver**, not this package's import
list. That distinction is the whole point of this guard, because the
first audit of this floor missed it.

That audit asked "what does this package import?", found four symbols
(``FeatureFrame``, ``FrameMetadata``, ``SpatialLevel``,
``SpatioTemporalIndex``) plus ``views_frames.conformance``, verified all
of them work at 1.0.0 in a clean venv, and concluded the floor could stay
at ``>=1.0``. Every step of that was true and the conclusion was wrong.

views-frames changed **how the summary statistics are computed**, three
times, none of it labelled breaking because it shipped MINOR:

===========  ====================================================
1.2.0        outside-in HDI tower + mass-aware tip
1.3.0        no magnitude-based zeroing by default
1.9.0        tower-tip MAP: ``tip_mass`` 0.5 -> 0.25 — "Behavior
             change to tower_point/summarize_tower outputs"
===========  ====================================================

``views_frames_summarize`` ships in the same wheel as ``views_frames``.
So a floor of ``>=1.0`` permits three different MAP/HDI semantics into
any environment resolving against it, and two systems on different
versions produce different numbers from the same posterior, silently.
We do not import the estimators — and that is irrelevant. We are a
widely-installed package; if we are the loosest constraint, we are the
one letting old semantics in.

1.9.0 is the strict minimum. The floor is 1.10.2 (see pyproject).

These guards are cheap: they do not reinstall old versions. They catch
the two ways the floor goes wrong — someone lowers it, or someone starts
importing a symbol outside the surface that was actually verified.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The surface verified by import against views-frames 1.0.0 on 2026-08-02,
# so it is available at the 1.10.2 floor a fortiori. Adding to this set is a
# claim that the new symbol exists at the declared floor — verify before
# widening. If a new import is an ESTIMATOR (map_estimate, hdi, quantiles,
# tower_point, summarize_*), stop: those have version-dependent semantics
# and pull the floor question open again.
AUDITED_SURFACE = {
    "FeatureFrame",
    "FrameMetadata",
    "SpatialLevel",
    "SpatioTemporalIndex",
    # from views_frames.conformance
    "assert_frame_contract",
    "CONFORMANCE_FLOOR",
}

AUDITED_FLOOR = "1.10.2"


def _declared_floor() -> str:
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    for dep in data["project"]["dependencies"]:
        if dep.startswith("views-frames"):
            m = re.search(r">=\s*([0-9][0-9.]*)", dep)
            assert m, f"Cannot parse a floor from {dep!r}"
            return m.group(1)
    raise AssertionError("views-frames is not in [project].dependencies")


def _imported_symbols() -> set[str]:
    """Every name this repo imports from views_frames, anywhere."""
    found: set[str] = set()
    for base in ("src", "scripts", "tests"):
        for path in (REPO / base).rglob("*.py"):
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError:  # pragma: no cover
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.split(".")[0] == "views_frames"
                ):
                    found.update(a.name for a in node.names)
    return found


class TestFloorMatchesUsage:
    def test_no_imports_outside_the_audited_surface(self) -> None:
        extra = _imported_symbols() - AUDITED_SURFACE
        assert not extra, (
            f"This repo imports {sorted(extra)} from views_frames, which is "
            f"outside the surface audited against the declared floor "
            f"({AUDITED_FLOOR}). Either confirm those symbols exist at the "
            f"floor and add them to AUDITED_SURFACE, or raise the floor to "
            f"the version that introduced them — and say which symbol forced "
            f"it. Note especially: if the new symbol is an estimator, its "
            f"NUMERIC OUTPUT is version-dependent (MAP/HDI changed in 1.2.0, "
            f"1.3.0 and 1.9.0) and the floor must sit above the change."
        )

    def test_declared_floor_is_the_audited_one(self) -> None:
        declared = _declared_floor()
        assert declared == AUDITED_FLOOR, (
            f"pyproject declares views-frames>={declared} but the audited "
            f"floor is {AUDITED_FLOOR}. If the raise is deliberate, name the "
            f"reason and update AUDITED_FLOOR plus the comment in "
            f"pyproject.toml. LOWERING it below 1.9.0 re-admits the "
            f"pre-amendment tower-tip MAP (tip_mass 0.5) and the 1.2.0/1.3.0 "
            f"HDI semantics — different numbers from the same posterior, "
            f"with no error. See C-337."
        )
