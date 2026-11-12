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

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_compilation.compilation_config import (
    CompilationConfig,
    FeatureSpec,
)
from datafactory_compilation.grid_compilation import compile_grid
from datafactory_priogrid.cell_generator import pgid_to_latlon
from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG
from datafactory_viewpoint.spatial_distribution import (
    get_spatial_distribution,
)
from datafactory_viewpoint.spatial_weights import build_spatial_weight_map

GAUL1 = Path("data/raw/gaul_admin/gaul1_code.parquet")
GAUL0 = Path("data/raw/gaul_admin/gaul0_code.parquet")

#: Cell 148759 is event 463131's regional centroid — the cell that held
#: 113,395 state-based fatalities in one month before this release.
TIGRAY_PGID = 148759

#: Cells of the admin-1 polygon containing TIGRAY_PGID, read from the
#: live crosswalk rather than hardcoded.
_POLYGON_WELL_LOCATED = (148039, 149477, 150197, 150199, 149479)

pytestmark = pytest.mark.skipif(
    not (GAUL1.exists() and GAUL0.exists()),
    reason=(
        "needs the GAUL crosswalks; a skip here is why this defect "
        "shipped, so it is stated rather than silent"
    ),
)


def _centroid(pgid: int) -> tuple[float, float]:
    lat, lon = pgid_to_latlon(np.array([pgid]), DEFAULT_GRID_CONFIG)
    return float(lat[0]), float(lon[0])


def _weight_map() -> object:
    """A weight map whose polygon has several well-located cells."""
    cells = [*_POLYGON_WELL_LOCATED, TIGRAY_PGID]
    table = pa.table({
        "where_prec": pa.array([1] * len(cells), pa.int64()),
        "priogrid_gid": pa.array(cells, pa.int64()),
        "best": pa.array([100, 200, 300, 150, 120, 180], pa.int64()),
    })
    return build_spatial_weight_map(table, GAUL1, GAUL0)


def _summary_event(month: str = "2021-12-01") -> dict:
    lat, lon = _centroid(TIGRAY_PGID)
    return {
        "id": 463131,
        "where_prec": 5,
        "date_prec": 5,
        "priogrid_gid": TIGRAY_PGID,
        "latitude": lat,
        "longitude": lon,
        "best": 113368,
        "low": 113368,
        "high": 113368,
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
            _summary_event(), _weight_map(),
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
            _summary_event(), _weight_map(),
        )
        slab = _compile(
            rows, tmp_path,
            date_field="date_month",
            pgid_field="priogrid_gid",
        )
        assert slab.max() < 113368, (
            f"one cell holds {slab.max():,.0f} of 113,368 — the "
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
            _summary_event(), _weight_map(),
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
            {**_summary_event(month=m), "best": 113368 // 12}
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
