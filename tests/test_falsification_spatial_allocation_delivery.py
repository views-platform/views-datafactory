"""Falsification: a spatial allocation that never reaches delivered data.

Written 2026-11-12 after the first production run under
``kgi_kti_activity``. The viewpoint parquet on the server held UCDP event
463131 across 18 cells and 12 months, summing to exactly 113,368. The
served grid held it in **one** cell.

The seam: ``spatial_distribution.proportional`` records its decision in
``priogrid_gid`` and leaves ``latitude``/``longitude`` at the original
centroid. ``grid_compilation._place_events`` never reads
``priogrid_gid`` — it recomputes the cell with
``latlon_to_pgid(lat, lon)``. Eighteen rows carrying identical
coordinates are therefore placed back into the single cell they came
from, and the allocation has no effect on anything a consumer can read.

Forty-seven tests exercise spatial distribution. None of them crosses
into compilation, which is why this shipped: the allocator is verified
to produce N cells, the compiler is verified to place events, and
nothing asserts that the N survives the handover.

Every test in this file is expected to FAIL until the seam is closed.
They are the acceptance criteria for that fix, not a description of
current behaviour.
"""

import logging
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import load_synthetic_generator

from datafactory_compilation.compilation_config import (
    CompilationConfig,
    FeatureSpec,
)
from datafactory_compilation.grid_compilation import compile_grid
from datafactory_priogrid.cell_generator import pgid_to_latlon
from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG
from datafactory_priogrid.temporal_generator import TemporalConfig
from datafactory_viewpoint.spatial_distribution import (
    get_spatial_distribution,
)
from datafactory_viewpoint.spatial_weights import build_spatial_weight_map

_GEN = load_synthetic_generator()

#: The cell the imprecise event names as its own location.
#:
#: The incident's cell was 148759, Tigray's regional centroid, which
#: held 113,395 state-based fatalities in a single month. This is a
#: synthetic cell instead (``scripts/generate_synthetic_data.py``):
#: nothing about the seam depends on which cell it is, and the real one
#: required the GAUL crosswalks, which ``.gitignore`` keeps out of CI.
#: A module-level ``skipif`` on those files is what made this defect
#: invisible for four months; #550 removed it.
SOURCE_PGID = _GEN.SUMMARY_EVENT_PGID

#: The cells a correct admin-1 allocation of that event must reach.
ALLOCATED_CELLS = _GEN.ADMIN1_ALLOCATION_CELLS

#: A polygon cell that is not the source cell, for the cases that need
#: coordinates resolving somewhere other than the declaration.
_OTHER_CELL = next(p for p in ALLOCATED_CELLS if p != SOURCE_PGID)


def _centroid(pgid: int) -> tuple[float, float]:
    lat, lon = pgid_to_latlon(np.array([pgid]), DEFAULT_GRID_CONFIG)
    return float(lat[0]), float(lon[0])


def _weight_map(tmp_path: Path) -> object:
    """A weight map over the synthetic polygon, built by the real code.

    The crosswalks and the well-located events are written under
    ``tmp_path`` by the synthetic generator, so these guards run with
    nothing under ``data/``. ``build_spatial_weight_map`` itself is the
    production function, unchanged.
    """
    gaul = _GEN.write_synthetic_gaul(tmp_path / "gaul_admin")
    events_path = tmp_path / "well_located.parquet"
    _GEN.write_synthetic_ucdp_events(events_path)
    return build_spatial_weight_map(
        pq.read_table(events_path),
        gaul["gaul1_code"],
        gaul["gaul0_code"],
    )


def _summary_event(month: str = "2021-12-01") -> dict:
    lat, lon = _centroid(SOURCE_PGID)
    return {
        "id": _GEN.SUMMARY_EVENT_ID,
        "where_prec": 5,
        "date_prec": 5,
        "priogrid_gid": SOURCE_PGID,
        "latitude": lat,
        "longitude": lon,
        "best": _GEN.SUMMARY_EVENT_BEST,
        "low": _GEN.SUMMARY_EVENT_BEST,
        "high": _GEN.SUMMARY_EVENT_BEST,
        "date_start": "2021-01-01",
        "date_end": "2021-12-31",
        "date_month": month,
        "type_of_violence": 1,
    }


def _compile(rows: list[dict], tmp_path: Path, **cfg_kwargs) -> np.ndarray:
    """Compile rows through the real compiler and return the feature slab."""
    keep = (
        "latitude", "longitude", "priogrid_gid",
        "date_month", "date_start",
        "best", "type_of_violence",
    )
    src = tmp_path / "viewpoint.parquet"
    pq.write_table(
        pa.Table.from_pylist([{k: r[k] for k in keep} for r in rows]),
        src,
    )
    config = CompilationConfig(
        source_path=src,
        # 2021 only. The default TemporalConfig spans 1989-2026, which
        # makes compile_grid zero-fill and save a 456x360x720 float32
        # grid -- about 473 MB written and another 473 MB copied into
        # RAM, per test. Every assertion below is identical at 1/456
        # the cost, and these guards are meant to run in CI.
        temporal_config=TemporalConfig(start_year=2021, end_year=2021),
        features=(
            FeatureSpec(
                "sb_best", "sum_field",
                value_field="best",
                filter={"type_of_violence": 1},
            ),
        ),
        output_dir=tmp_path / "compiled",
        ledger_path=tmp_path / "ledger.jsonl",
        **cfg_kwargs,
    )
    compile_grid(config)
    grid = np.load(tmp_path / "compiled" / "grid.npy", mmap_mode="r")
    return np.asarray(grid[..., 0])


class TestAllocationSurvivesCompilation:
    """The allocator's decision must reach the grid."""

    def test_spatial_allocation_reaches_the_compiled_grid(
        self, tmp_path: Path,
    ) -> None:
        """The number of cells the allocator chose must be delivered.

        FAILS TODAY: the allocator returns one row per cell, every row
        carrying the source centroid's coordinates, and the compiler
        places all of them into that one cell.
        """
        rows = get_spatial_distribution("proportional")(
            _summary_event(), _weight_map(tmp_path),
        )
        allocated = {r["priogrid_gid"] for r in rows}
        assert len(allocated) > 1, (
            "premise guard: the allocator must spread this event"
        )

        slab = _compile(
            rows, tmp_path,
            date_field="date_month",
            pgid_field="priogrid_gid",
        )
        delivered = int(np.sum(slab > 0))

        assert delivered == len(allocated), (
            f"allocator chose {len(allocated)} cells, grid delivered "
            f"{delivered}. The allocation was recorded in "
            f"'priogrid_gid' and compilation reads "
            f"'latitude'/'longitude'."
        )

    def test_no_single_cell_holds_the_whole_summary_event(
        self, tmp_path: Path,
    ) -> None:
        """No delivered cell may carry the event's entire total.

        FAILS TODAY: exactly one cell carries all 113,368.
        """
        rows = get_spatial_distribution("proportional")(
            _summary_event(), _weight_map(tmp_path),
        )
        slab = _compile(
            rows, tmp_path,
            date_field="date_month",
            pgid_field="priogrid_gid",
        )
        # Premise first: an empty grid has max 0.0, which would satisfy
        # the assertion below while nothing at all was delivered. If a
        # future change drops these rows instead of misplacing them --
        # skipped spatially, or a month outside the temporal range --
        # this guard would go green on a total absence.
        assert slab.sum() == pytest.approx(_GEN.SUMMARY_EVENT_BEST), (
            f"delivered {slab.sum():,.0f} of "
            f"{_GEN.SUMMARY_EVENT_BEST:,} -- the rows were "
            f"dropped, not placed, so the maximum below proves nothing"
        )
        assert slab.max() < _GEN.SUMMARY_EVENT_BEST, (
            f"one cell holds {slab.max():,.0f} of "
            f"{_GEN.SUMMARY_EVENT_BEST:,} — the "
            f"allocation did not survive compilation"
        )

    def test_the_compiler_used_the_declared_cell_not_the_coordinates(
        self, tmp_path: Path,
    ) -> None:
        """Delivery must follow the declaration, not the coordinates.

        This replaces an earlier test that asserted each allocated row's
        coordinates agree with its own ``priogrid_gid``. That would be
        the acceptance criterion for a different fix -- rewriting the
        coordinates to the assigned cell's centroid. The fix taken
        instead makes the declared cell authoritative and leaves the
        coordinates honest to the source event, so those rows are
        *expected* to disagree, and asserting otherwise would forbid the
        chosen design.

        What must hold either way is this: the cell the grid actually
        used is the one the allocator chose. Asserted by giving every
        row coordinates that resolve to one cell and a declared cell
        that resolves elsewhere -- so coordinate-derived placement and
        declaration-derived placement cannot be confused.
        """
        rows = get_spatial_distribution("proportional")(
            _summary_event(), _weight_map(tmp_path),
        )
        allocated = sorted({r["priogrid_gid"] for r in rows})
        assert len(allocated) > 1, (
            "premise guard: the allocator must spread this event"
        )

        slab = _compile(
            rows, tmp_path,
            date_field="date_month",
            pgid_field="priogrid_gid",
        )
        # The slab is [T, NROW, NCOL]; summing over time and flattening
        # row-major gives index row*NCOL + col, and pgid is that plus 1.
        delivered = {
            int(i) + 1
            for i in np.flatnonzero(slab.sum(axis=0).reshape(-1))
        }

        source_cell = _summary_event()["priogrid_gid"]
        assert delivered == set(allocated), (
            f"allocator chose {allocated}, grid delivered "
            f"{sorted(delivered)}"
        )
        assert delivered != {source_cell}, (
            "every row collapsed back onto the source cell -- the "
            "declaration was ignored and the coordinates won"
        )


class TestTemporalAxisHasTheSameSeam:
    """The temporal twin: latent, and one default away from biting."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Known, measured and deliberately not closed in a patch "
            "release. CompilationConfig.date_field defaults to "
            "date_start while the temporal allocator writes "
            "date_month, so a caller taking the default on an "
            "allocated source collapses every distributed month. The "
            "clean fix is to make the argument required, which is a "
            "breaking change to a class exported in "
            "datafactory_compilation.__all__ and therefore owed to a "
            "MAJOR release. #552 closed every path inside this "
            "repository instead -- see "
            "tests/test_falsification_temporal_field_authority.py -- "
            "and this marker records the residual: an EXTERNAL library "
            "caller, on an allocated parquet, taking the default. "
            "strict=True so that whoever does make the default safe is "
            "forced to remove the marker rather than leaving a stale "
            "xfail behind."
        ),
    )
    def test_temporal_allocation_survives_the_library_default(
        self, tmp_path: Path,
    ) -> None:
        """Allocation must not depend on which date field a caller picks.

        ``CompilationConfig.date_field`` defaults to ``date_start``.
        The temporal allocator writes ``date_month`` and leaves
        ``date_start`` untouched, so a caller taking the library default
        collapses every distributed month back onto the event's start
        month — the exact failure the spatial axis actually suffered.
        The production pipeline is saved only by ``compile_grid.py``'s
        argparse default being ``date_month``.

        FAILS TODAY: one month receives everything.
        """
        months = [f"2021-{m:02d}-01" for m in range(1, 13)]
        rows = [
            {**_summary_event(month=m), "best": _GEN.SUMMARY_EVENT_BEST // 12}
            for m in months
        ]
        slab = _compile(rows, tmp_path)  # library default date_field
        populated = int(np.sum(slab.sum(axis=tuple(range(1, slab.ndim))) > 0))
        assert populated == len(months), (
            f"{len(months)} allocated months, {populated} delivered — "
            f"the allocation depends on the caller's date_field"
        )


class TestTheCompilerCanBeToldTheCellIsDecided:
    """The structural gap, stated as a test."""

    def test_compilation_config_can_name_a_precomputed_cell_field(
        self,
    ) -> None:
        """There must be a way to say 'the cell is already decided'.

        ``CompilationConfig`` exposes ``lat_field`` and ``lon_field``
        and nothing else. An upstream stage that has already decided an
        event's cell has no way to communicate it, which is why the
        allocation is silently discarded rather than rejected.

        FAILS TODAY: no such field exists.
        """
        fields = set(CompilationConfig.__dataclass_fields__)
        assert fields & {"pgid_field", "cell_field"}, (
            "CompilationConfig offers only coordinate-based placement; "
            f"available fields: {sorted(fields)}"
        )


class TestUnusableDeclaredCellRed:
    """The one remaining path that can silently discard an allocation.

    A declared cell that is present but unusable -- not an integer, 0,
    or above ``n_cells`` -- falls back to ``latitude``/``longitude``,
    which for an allocated row is the stale source centroid the
    allocator never updated. That is the original defect's failure mode
    exactly, reached by a different route.

    ``docs/CICs/CompilationConfig.md`` now *guarantees* that such rows
    are counted apart from rows carrying no decision, and that any
    unusable value is reported. Nothing exercised it: the tests above
    all pass clean in-range cells. A guarantee no test touches is a
    sentence, not a contract.
    """

    def _rows(self, declared: list[object]) -> list[dict]:
        """One row per declared value, each with distinct coordinates."""
        out = []
        for n, value in enumerate(declared):
            lat, lon = _centroid(_OTHER_CELL)
            out.append({
                **_summary_event(),
                "priogrid_gid": value,
                "latitude": lat,
                "longitude": lon + n * 0.5,
                "best": 10,
            })
        return out

    @pytest.mark.parametrize(
        "bad", [0, -1, 259_201, 999_999_999],
        ids=["zero", "negative", "one-past-the-end", "absurd"],
    )
    def test_an_out_of_range_declared_cell_is_not_used(
        self, tmp_path: Path, bad: int,
    ) -> None:
        """It must fall back, not clamp, and not place at `bad`.

        ADR-024's Invariant 2 clamps an out-of-bounds *coordinate* to
        the nearest valid cell. That leniency is deliberately not
        extended to a declared cell, because a declared cell outside
        the grid is a data error rather than a near-miss.
        """
        slab = _compile(
            self._rows([bad]), tmp_path,
            date_field="date_month",
            pgid_field="priogrid_gid",
        )
        delivered = {
            int(i) + 1
            for i in np.flatnonzero(slab.sum(axis=0).reshape(-1))
        }
        assert delivered, "the row was dropped entirely"
        assert bad not in delivered, (
            f"an out-of-range declared cell {bad} was used as a cell"
        )
        # It fell back to the coordinates, which resolve to this cell.
        assert delivered == {_OTHER_CELL}, (
            f"expected the coordinate fallback, got {delivered}"
        )
        assert slab.sum() == pytest.approx(10)

    def test_unusable_declared_cells_are_reported(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Any unusable value warns -- not a majority of them.

        The first version of this warning fired only when fallbacks
        outnumbered uses, so a source with 49% corrupt declared cells
        was silent. There is no benign rate: the allocator either
        decided a placeable cell or it did not.
        """
        rows = self._rows([*ALLOCATED_CELLS[:3], 0])
        with caplog.at_level(logging.INFO):
            _compile(
                rows, tmp_path,
                date_field="date_month",
                pgid_field="priogrid_gid",
            )
        text = caplog.text
        assert "3 rows used the declared cell" in text, text[-500:]
        assert "1 were unusable" in text, text[-500:]
        assert "was unusable on 1 of 4 rows" in text, (
            "one corrupt cell in four did not warn, so the warning "
            "only fires on a majority -- which is the defect it "
            "replaced"
        )

    def test_a_row_carrying_no_declared_cell_is_counted_apart(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A null is normal; conflating it with corruption hides both."""
        rows = self._rows([ALLOCATED_CELLS[0], None])
        with caplog.at_level(logging.INFO):
            _compile(
                rows, tmp_path,
                date_field="date_month",
                pgid_field="priogrid_gid",
            )
        assert "1 had none, 0 were unusable" in caplog.text, (
            caplog.text[-500:]
        )
        assert "was unusable on" not in caplog.text, (
            "a row with no declared cell triggered the corruption "
            "warning; absent and invalid are not the same thing"
        )
