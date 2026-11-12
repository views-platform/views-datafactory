"""Falsification: a temporal allocation nullified by an omitted argument.

Source: views-datafactory#552, epic #547, 2026-11-12.

Claim under test: "the temporal allocation reaches the grid regardless of
which date column a caller happens to bind."

**Verdict: FALSIFIED as stated, and only partly repairable in a patch
release.** The seam is real. ``temporal_distribution`` writes its decision
to ``date_month`` and leaves ``date_start``/``date_end`` untouched, while
``CompilationConfig.date_field`` defaults to ``date_start``. A caller
taking that default on an allocated source collapses every distributed
month onto the event's start month, conserves totals while doing it, and
reports success -- the temporal twin of the spatial defect in #551, which
discarded the placement of 26.49% of UCDP fatality mass.

Production survives only because ``scripts/compile_grid.py``'s argparse
default is ``date_month``, and both ACLED call sites name ``event_date``
explicitly.

**What this file does NOT assert, and why.** The clean fix is to make
``date_field`` a required argument. It is not done here:
``CompilationConfig`` is exported in ``datafactory_compilation.__all__``
and ships in the wheel, so removing the default breaks external callers
and is owed to a MAJOR release. An auto-detecting default -- ``None``
meaning "use ``date_month`` when the source has one" -- would have cost
nothing and was rejected, because inferring decision-relevant semantics
is exactly what ADR-003 forbids, and this defect does not deserve to be
fixed by a second instance of its own cause.

So the residual hazard is: **an external library caller, compiling an
allocated parquet, taking the default.** Registered rather than closed.
What is closed is every path inside this repository, by the two guards
below.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_compilation.compilation_config import CompilationConfig
from datafactory_compilation.preflight import (
    reject_ignored_allocation,
)

#: Scripts are the production entry points. A future one that takes the
#: default is the failure this file exists to prevent.
#:
#: Anchored to this file rather than to the working directory. The first
#: version used ``Path("scripts")``, which is CWD-relative: run from
#: anywhere but the repository root the glob matched nothing, ``offenders``
#: came back empty, and the guard passed while checking zero files.
#: Demonstrated by running pytest from ``/tmp``. That is mutation
#: category M1 -- vacuous by construction -- in a guard written to
#: prevent exactly that class of defect, so the premise guard below is
#: not decoration.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"

#: Scanning fewer than this many scripts means the scan is not looking at
#: the repository. The real count is far higher; this is a floor that
#: catches a broken path, not an inventory.
_MIN_SCRIPTS_SCANNED = 20

def _configs_omitting(path: Path, keyword: str) -> list[int]:
    """Line numbers of CompilationConfig calls that omit `keyword`.

    Parsed rather than pattern-matched. The first version of this used a
    regex and reported nine false positives: it stopped at the closing
    paren of an inner ``FeatureSpec`` tuple, truncating the argument list
    before ``date_field`` appeared, and it matched inside
    ``PregriddedCompilationConfig`` -- which takes ``month_id_field``
    and has no business here. Balancing parens is a parser's job.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute)
            else None
        )
        if name != "CompilationConfig":
            continue
        if not any(kw.arg == keyword for kw in node.keywords):
            offenders.append(node.lineno)
    return offenders


class TestProductionCallSitesNameTheirDateFieldGreen:
    """Every script constructing a compile must say which date it means."""

    def test_no_script_takes_the_date_field_default(self) -> None:
        """A production call site must name ``date_field`` explicitly.

        This is the guard that stands in for the required argument we
        cannot add in a patch release. It catches the realistic future
        failure -- someone adding a second UCDP-shaped compile script
        and inheriting a default that silently discards allocation.
        """
        scanned = sorted(_SCRIPTS.rglob("*.py"))
        assert len(scanned) >= _MIN_SCRIPTS_SCANNED, (
            f"only {len(scanned)} scripts found under {_SCRIPTS} -- the "
            f"scan is not looking at the repository, so a pass here "
            f"would mean nothing"
        )
        offenders = [
            f"{path.relative_to(_REPO_ROOT)}:{line}"
            for path in scanned
            for line in _configs_omitting(path, "date_field")
        ]

        assert not offenders, (
            "these production call sites inherit "
            f"CompilationConfig.date_field='{CompilationConfig.date_field}', "
            "a raw field, so an allocated source would be silently "
            "collapsed onto its start month: " + ", ".join(offenders)
        )

    def test_no_script_takes_the_pgid_field_default(self) -> None:
        """Same requirement on the spatial axis, for the same reason.

        ``pgid_field`` defaults to ``None``, which places purely by
        coordinates. On a source whose cells were decided upstream that
        silently discards every decision -- the defect this epic exists
        for. A script that means to place by coordinates must say so by
        passing ``pgid_field=None`` explicitly, which is a declaration
        rather than an inherited default.

        The temporal half of this guard was written first and the
        spatial half was not, which is how a guard protects the axis
        nobody got wrong.
        """
        scanned = sorted(_SCRIPTS.rglob("*.py"))
        assert len(scanned) >= _MIN_SCRIPTS_SCANNED, (
            f"only {len(scanned)} scripts found under {_SCRIPTS}"
        )
        offenders = [
            f"{path.relative_to(_REPO_ROOT)}:{line}"
            for path in scanned
            for line in _configs_omitting(path, "pgid_field")
        ]

        assert not offenders, (
            "these production call sites inherit "
            "CompilationConfig.pgid_field=None, so a source that "
            "declares its cells would be placed by coordinates and "
            "every allocation discarded: " + ", ".join(offenders)
        )

    def test_the_hazardous_default_is_still_what_we_think_it_is(
        self,
    ) -> None:
        """Premise guard for the test above.

        If the default ever becomes ``date_month``, the call-site guard
        is no longer protecting anything and this file should be
        reconsidered rather than left asserting a resolved hazard. If it
        becomes required, the construction above raises and the guard is
        likewise obsolete.
        """
        assert CompilationConfig.date_field == "date_start", (
            "CompilationConfig.date_field is no longer 'date_start' -- "
            "re-read this module's docstring and retire or rewrite it"
        )


class TestCompileRefusesToDiscardAnAllocationRed:
    """The entry point must refuse, not warn, and not proceed."""

    def _allocated_parquet(self, path: Path) -> Path:
        """A source carrying date_month, i.e. one that was allocated."""
        pq.write_table(
            pa.table({
                "latitude": [4.0, 4.0],
                "longitude": [4.0, 4.0],
                "priogrid_gid": [100_000, 100_001],
                "date_start": ["2021-01-01", "2021-01-01"],
                "date_month": ["2021-01-01", "2021-06-01"],
                "best": [10, 10],
                "type_of_violence": [1, 1],
            }),
            path,
        )
        return path

    def test_binding_a_raw_date_on_an_allocated_source_is_refused(
        self, tmp_path: Path,
    ) -> None:
        """Exit non-zero, and say why in terms a reader can act on."""
        source = self._allocated_parquet(tmp_path / "allocated.parquet")
        result = subprocess.run(
            [
                sys.executable, "scripts/compile_grid.py",
                "--source", str(source),
                "--date-field", "date_start",
                "--output-dir", str(tmp_path / "out"),
                "--provenance-dir", str(tmp_path / "prov"),
            ],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode != 0, (
            "compiling an allocated source on a raw date field "
            "succeeded; it must refuse"
        )
        combined = result.stdout + result.stderr
        assert "date_month" in combined
        assert "temporally allocated" in combined, (
            f"the refusal did not explain itself: {combined[-400:]}"
        )

    def test_a_source_without_date_month_is_not_refused(
        self, tmp_path: Path,
    ) -> None:
        """The guard must not fire on pre-allocation data.

        A raw harvester snapshot has no ``date_month``, so binding
        ``date_start`` is correct there and must stay allowed. Without
        this, the guard would be indistinguishable from banning
        ``date_start`` outright.
        """
        source = tmp_path / "raw.parquet"
        pq.write_table(
            pa.table({
                "latitude": [4.0],
                "longitude": [4.0],
                "date_start": ["2021-01-01"],
                "best": [10],
                "type_of_violence": [1],
            }),
            source,
        )
        assert reject_ignored_allocation(source, "date_start") is None

    def test_naming_the_allocation_field_is_not_refused(
        self, tmp_path: Path,
    ) -> None:
        """The correct configuration must pass the guard."""
        source = self._allocated_parquet(tmp_path / "allocated.parquet")
        assert reject_ignored_allocation(source, "date_month") is None


@pytest.mark.parametrize("date_field", ["date_start", "date_end"])
def test_the_refusal_names_whichever_raw_field_was_bound(
    tmp_path: Path, date_field: str,
) -> None:
    """The message must name the field the caller actually passed.

    A guard that fires and then misreports is category M7: it sends the
    reader to the wrong place. Parameterised because an enumeration of
    one is not an enumeration.
    """
    source = tmp_path / "allocated.parquet"
    pq.write_table(
        pa.table({
            "latitude": [4.0],
            "longitude": [4.0],
            "date_start": ["2021-01-01"],
            "date_end": ["2021-12-31"],
            "date_month": ["2021-06-01"],
            "best": [10],
            "type_of_violence": [1],
        }),
        source,
    )
    message = reject_ignored_allocation(source, date_field)
    assert message is not None
    assert f"'{date_field}'" in message, (
        f"refusal did not name the bound field: {message}"
    )
