"""Generate synthetic compiled grids with planted known-answer values.

Creates a minimal directory structure that assembly, zarr export, and
consumer scripts can process. Used for fast end-to-end testing (~seconds
instead of ~hours) and known-answer verification at every layer boundary.

Usage:
    uv run python scripts/generate_synthetic_data.py [--output-dir /tmp/synthetic]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from datafactory_priogrid.cell_generator import pgid_to_latlon
from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG

# ── Grid constants ──────────────────────────────────────────
NROW, NCOL = 360, 720

# ── Planted cells (both must be in land_pgids) ─────────────
# Near Nairobi: lat≈-1.2°, lon≈36.8° and lon≈37.2°
ROW_A, COL_A = 177, 433  # pgid = 127874
ROW_B, COL_B = 177, 434  # pgid = 127875
PGID_A = ROW_A * NCOL + COL_A + 1
PGID_B = ROW_B * NCOL + COL_B + 1

# ── Temporal ranges ─────────────────────────────────────────
UCDP_MONTHS = np.arange("2020-01", "2021-01", dtype="datetime64[M]")  # 12
ACLED_MONTHS = np.arange("2020-04", "2020-10", dtype="datetime64[M]")  # 6

UCDP_FEATURES = ["ged_sb_best", "ged_ns_best", "ged_os_best"]
ACLED_FEATURES = ["acled_count", "acled_fatalities"]

# ── Planted values ──────────────────────────────────────────
# Format: (row, col, time_idx, feature_idx, value)
UCDP_PLANTS = [
    (ROW_A, COL_A, 0, 0, 7.0),    # ged_sb_best, Jan 2020
    (ROW_A, COL_A, 0, 1, 3.0),    # ged_ns_best, Jan 2020
    (ROW_A, COL_A, 0, 2, 1.0),    # ged_os_best, Jan 2020
    (ROW_A, COL_A, 6, 0, 11.0),   # ged_sb_best, Jul 2020
    (ROW_A, COL_A, 6, 1, 5.0),    # ged_ns_best, Jul 2020
    (ROW_A, COL_A, 6, 2, 2.0),    # ged_os_best, Jul 2020
    (ROW_B, COL_B, 0, 0, 99.0),   # ged_sb_best, Jan 2020 (cell B)
]

ACLED_PLANTS = [
    (ROW_A, COL_A, 0, 0, 4.0),    # acled_count, Apr 2020 (ACLED month 0)
    (ROW_A, COL_A, 0, 1, 8.0),    # acled_fatalities, Apr 2020
    (ROW_A, COL_A, 3, 0, 6.0),    # acled_count, Jul 2020 (ACLED month 3)
    (ROW_A, COL_A, 3, 1, 12.0),   # acled_fatalities, Jul 2020
]

STATIC_PLANTS = {
    PGID_A: 1250.0,
    PGID_B: 500.0,
}

ADMIN_PLANTS = {
    PGID_A: 133,
    PGID_B: 133,
}


def _pgid(row: int, col: int) -> int:
    """Grid cell id for a (row, col), row-major and 1-based."""
    return row * NCOL + col + 1


# ── Synthetic geography for the spatial allocator ───────────
# A proportional allocation needs somewhere to go: an admin-1 polygon
# holding several cells, some of which carry well-located fatalities.
# The real Tigray polygon that exposed the delivery defect holds 18
# cells; eight proves the mechanism, and a contiguous block keeps the
# geometry obvious when a test fails.
#
# Rows 200-203, columns 400-403 of the 360x720 grid -- centroids
# 10.25-11.75N, 20.25-21.75E. Verified 2026-11-12 that every one of the
# sixteen cells round-trips pgid -> centroid -> pgid, which the
# compiler's coordinate fallback depends on. Deliberately clear of
# PGID_A/PGID_B (rows 177) so the existing assembly plants are
# untouched.
GAUL0_CODE = 900  # the synthetic country
GAUL1_CODE_A = 9001  # admin-1 polygon A
GAUL1_CODE_B = 9002  # admin-1 polygon B, same country

GAUL1_POLYGON_A: tuple[int, ...] = tuple(
    _pgid(r, c) for r in (200, 201) for c in range(400, 404)
)
GAUL1_POLYGON_B: tuple[int, ...] = tuple(
    _pgid(r, c) for r in (202, 203) for c in range(400, 404)
)

#: The cell an imprecise event names as its own location. Inside
#: polygon A, so an admin-1 allocation has the rest of A to spread into.
SUMMARY_EVENT_PGID = GAUL1_POLYGON_A[0]

#: Cells carrying well-located fatalities, and how many each carries.
#: Unequal on purpose: equal weights cannot distinguish a proportional
#: allocation from the uniform fallback that fires when a polygon has
#: no well-located mass at all. Two cells of A (indices 6 and 7) carry
#: none, so the allocated set is a strict subset of the polygon --
#: a test that counted polygon cells instead of weighted cells would
#: be wrong by two.
WELL_LOCATED_FATALITIES: dict[int, int] = {
    SUMMARY_EVENT_PGID: 180,
    GAUL1_POLYGON_A[1]: 100,
    GAUL1_POLYGON_A[2]: 200,
    GAUL1_POLYGON_A[3]: 300,
    GAUL1_POLYGON_A[4]: 150,
    GAUL1_POLYGON_A[5]: 120,
    GAUL1_POLYGON_B[0]: 500,
    GAUL1_POLYGON_B[1]: 250,
}

#: Cells a where_prec<=5 allocation of SUMMARY_EVENT_PGID's event can
#: reach: the weighted cells of polygon A only.
ADMIN1_ALLOCATION_CELLS: tuple[int, ...] = tuple(
    sorted(p for p in WELL_LOCATED_FATALITIES if p in GAUL1_POLYGON_A)
)

#: Cells a where_prec==6 allocation can reach: every weighted cell in
#: the country. Strictly larger than ADMIN1_ALLOCATION_CELLS, so a test
#: can tell admin-1 placement from country placement.
COUNTRY_ALLOCATION_CELLS: tuple[int, ...] = tuple(
    sorted(WELL_LOCATED_FATALITIES)
)

# ── Synthetic UCDP events ───────────────────────────────────
PRECISE_EVENT_ID_BASE = 910_000
ADMIN1_EVENT_ID = 900_004
SUMMARY_EVENT_ID = 900_005
COUNTRY_EVENT_ID = 900_006

#: Kept at the real event 463131's total so that a failure message in
#: the delivery guards reads against the measured incident rather than
#: an invented number.
SUMMARY_EVENT_BEST = 113_368

#: One dyad, one conflict, one side_b, one country for every synthetic
#: event, so the temporal cascade has a populated bucket at each level.
CASCADE_IDS: dict[str, int] = {
    "dyad_new_id": 9100,
    "conflict_new_id": 9200,
    "side_b_new_id": 9300,
    "country_id": GAUL0_CODE,
}


def _make_pgids() -> np.ndarray:
    pgids = np.zeros((NROW, NCOL), dtype=np.int32)
    for row in range(NROW):
        for col in range(NCOL):
            pgids[row, col] = row * NCOL + col + 1
    return pgids


def _make_grid(
    shape: tuple[int, ...],
    plants: list[tuple[int, int, int, int, float]],
) -> np.ndarray:
    grid = np.zeros(shape, dtype=np.float32)
    for row, col, t, f, val in plants:
        grid[t, row, col, f] = val
    return grid


def _centroid(pgid: int) -> tuple[float, float]:
    """The cell's centre, from the grid authority rather than re-derived.

    Using ``pgid_to_latlon`` rather than arithmetic matters: the
    compiler's coordinate fallback calls ``latlon_to_pgid``, and a
    fixture that derived centroids its own way could disagree with the
    code under test about which cell a coordinate names.
    """
    lat, lon = pgid_to_latlon(np.array([pgid]), DEFAULT_GRID_CONFIG)
    return float(lat[0]), float(lon[0])


def write_synthetic_gaul(admin_dir: Path) -> dict[str, Path]:
    """Write a synthetic GAUL crosswalk pair over the planted block.

    Two columns, ``gid`` and ``value`` -- the real files' schema, so
    ``spatial_weights._load_gaul_crosswalk`` needs no change and the
    paths can be handed straight to ``build_spatial_weight_map``.

    Written to its own directory, never to the assembly's
    ``raw/gaul_admin``: ``assemble_grid.py`` turns every crosswalk it
    finds there into a grid channel (``admin_numeric_fields``), so
    dropping a ``gaul1_code`` beside the assembly's ``gaul0_code``
    silently adds a feature and shifts the channel order that
    ``tests/test_synthetic_pipeline.py`` asserts on. The allocator and
    the assembly are different consumers of GAUL and get separate
    fixtures.

    Writing this pair under a ``tmp_path`` is what lets the spatial
    guards run with nothing under ``data/``.
    """
    admin_dir.mkdir(parents=True, exist_ok=True)

    polygon_cells = (*GAUL1_POLYGON_A, *GAUL1_POLYGON_B)
    gaul0_rows: dict[int, int] = dict.fromkeys(
        polygon_cells, GAUL0_CODE,
    )
    gaul1_rows: dict[int, int] = {
        **dict.fromkeys(GAUL1_POLYGON_A, GAUL1_CODE_A),
        **dict.fromkeys(GAUL1_POLYGON_B, GAUL1_CODE_B),
    }

    paths: dict[str, Path] = {}
    for name, rows in (
        ("gaul0_code", gaul0_rows),
        ("gaul1_code", gaul1_rows),
    ):
        path = admin_dir / f"{name}.parquet"
        pd.DataFrame({
            "gid": list(rows.keys()),
            "value": list(rows.values()),
        }).to_parquet(path, index=False)
        paths[name] = path
    return paths


def _synthetic_event(
    event_id: int,
    *,
    pgid: int,
    best: int,
    where_prec: int,
    date_prec: int,
    date_start: str,
    date_end: str | None = None,
) -> dict:
    """One UCDP-shaped event at a cell's centroid.

    Same field set as ``tests/conftest.py``'s ``make_ucdp_event``, plus
    the three non-country cascade keys, so a table of these satisfies
    both ``build_spatial_weight_map`` and
    ``build_temporal_weight_map``.
    """
    lat, lon = _centroid(pgid)
    return {
        "id": event_id,
        "latitude": lat,
        "longitude": lon,
        "priogrid_gid": pgid,
        "date_start": date_start,
        "date_end": date_end or date_start,
        "date_prec": date_prec,
        "where_prec": where_prec,
        "best": best,
        "low": best,
        "high": best,
        "type_of_violence": 1,
        "_source_type": "annual",
        "_source_version": "25.1",
        "_ingested_at": "2026-11-12T00:00:00Z",
        **CASCADE_IDS,
    }


def write_synthetic_ucdp_events(path: Path) -> list[dict]:
    """Write a synthetic UCDP event parquet and return its rows.

    Contents, in the order the allocator needs them:

    - one precise event (``where_prec=1``, ``date_prec=1``) per entry in
      ``WELL_LOCATED_FATALITIES``, which is what seeds both weight maps.
      Their months are spread across 2021 so the temporal cascade has
      more than one bucket to choose between.
    - an admin-1-only event (``where_prec=4``).
    - a month-imprecise summary event (``where_prec=5``,
      ``date_prec=5``) spanning all of 2021 -- the shape of the event
      that exposed the delivery defect.
    - a country-only event (``where_prec=6``).

    Every imprecise event names ``SUMMARY_EVENT_PGID`` as its location,
    so its coordinates and its allocated cells necessarily differ.
    """
    events: list[dict] = [
        _synthetic_event(
            PRECISE_EVENT_ID_BASE + n,
            pgid=pgid,
            best=deaths,
            where_prec=1,
            date_prec=1,
            date_start=f"2021-{(n % 12) + 1:02d}-05",
        )
        for n, (pgid, deaths) in enumerate(
            sorted(WELL_LOCATED_FATALITIES.items())
        )
    ]
    events.append(_synthetic_event(
        ADMIN1_EVENT_ID,
        pgid=SUMMARY_EVENT_PGID,
        best=1_000,
        where_prec=4,
        date_prec=1,
        date_start="2021-06-15",
    ))
    events.append(_synthetic_event(
        SUMMARY_EVENT_ID,
        pgid=SUMMARY_EVENT_PGID,
        best=SUMMARY_EVENT_BEST,
        where_prec=5,
        date_prec=5,
        date_start="2021-01-01",
        date_end="2021-12-31",
    ))
    events.append(_synthetic_event(
        COUNTRY_EVENT_ID,
        pgid=SUMMARY_EVENT_PGID,
        best=400,
        where_prec=6,
        date_prec=1,
        date_start="2021-03-10",
    ))

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(events).to_parquet(path, index=False)
    return events


def generate(output_dir: Path) -> dict:
    """Create synthetic compiled grids with planted known-answer values.

    Returns metadata dict with planted values for assertion.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── UCDP compiled grid ──────────────────────────────────
    ucdp_dir = output_dir / "compiled"
    ucdp_dir.mkdir(parents=True, exist_ok=True)

    n_t = len(UCDP_MONTHS)
    n_f = len(UCDP_FEATURES)
    ucdp_grid = _make_grid((n_t, NROW, NCOL, n_f), UCDP_PLANTS)
    np.save(ucdp_dir / "grid.npy", ucdp_grid)

    pgids = _make_pgids()
    np.save(ucdp_dir / "pgids.npy", pgids)
    np.save(ucdp_dir / "time_steps.npy", UCDP_MONTHS)
    (ucdp_dir / "feature_names.json").write_text(json.dumps(UCDP_FEATURES))

    print(f"UCDP: [{n_t}, {NROW}, {NCOL}, {n_f}] = {ucdp_grid.nbytes / 1e6:.0f} MB")

    # ── ACLED compiled grid ─────────────────────────────────
    acled_dir = ucdp_dir / "acled"
    acled_dir.mkdir(parents=True, exist_ok=True)

    n_t_acled = len(ACLED_MONTHS)
    n_f_acled = len(ACLED_FEATURES)
    acled_grid = _make_grid((n_t_acled, NROW, NCOL, n_f_acled), ACLED_PLANTS)
    np.save(acled_dir / "grid.npy", acled_grid)

    np.save(acled_dir / "pgids.npy", pgids)
    np.save(acled_dir / "time_steps.npy", ACLED_MONTHS)
    (acled_dir / "feature_names.json").write_text(json.dumps(ACLED_FEATURES))

    acled_mb = acled_grid.nbytes / 1e6
    print(f"ACLED: [{n_t_acled}, {NROW}, {NCOL}, {n_f_acled}] = {acled_mb:.0f} MB")

    # ── Static variables ────────────────────────────────────
    static_dir = output_dir / "raw" / "priogrid_static"
    static_dir.mkdir(parents=True, exist_ok=True)

    static_df = pd.DataFrame({
        "gid": list(STATIC_PLANTS.keys()),
        "value": list(STATIC_PLANTS.values()),
    })
    static_df.to_parquet(static_dir / "landarea.parquet", index=False)
    print(f"Static: {len(static_df)} cells")

    # ── Admin boundaries, for assembly ──────────────────────
    admin_dir = output_dir / "raw" / "gaul_admin"
    admin_dir.mkdir(parents=True, exist_ok=True)

    admin_df = pd.DataFrame({
        "gid": list(ADMIN_PLANTS.keys()),
        "value": list(ADMIN_PLANTS.values()),
    })
    admin_df.to_parquet(admin_dir / "gaul0_code.parquet", index=False)
    print(f"Admin: {len(admin_df)} cells")

    # ── Geography and events, for the allocator ─────────────
    # Deliberately not under raw/gaul_admin -- see
    # write_synthetic_gaul's docstring.
    allocator_dir = output_dir / "allocator"
    gaul_paths = write_synthetic_gaul(allocator_dir / "gaul_admin")
    events_path = allocator_dir / "ucdp_events.parquet"
    events = write_synthetic_ucdp_events(events_path)
    n_polygon = len(GAUL1_POLYGON_A) + len(GAUL1_POLYGON_B)
    print(
        f"Allocator: {n_polygon} polygon cells, "
        f"{len(events)} synthetic UCDP events"
    )

    total_mb = (ucdp_grid.nbytes + acled_grid.nbytes) / 1e6
    print(f"Total: {total_mb:.0f} MB")

    return {
        "row_a": ROW_A,
        "col_a": COL_A,
        "row_b": ROW_B,
        "col_b": COL_B,
        "pgid_a": PGID_A,
        "pgid_b": PGID_B,
        "ucdp_features": UCDP_FEATURES,
        "acled_features": ACLED_FEATURES,
        "acled_offset": 3,
        "n_months": len(UCDP_MONTHS),
        "gaul0_path": gaul_paths["gaul0_code"],
        "gaul1_path": gaul_paths["gaul1_code"],
        "events_path": events_path,
        "n_events": len(events),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic compiled grids for testing"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/synthetic_pipeline"),
    )
    args = parser.parse_args()

    meta = generate(args.output_dir)
    print(f"\nOutput: {args.output_dir}")
    print(f"Cell A: pgid={meta['pgid_a']} (row={meta['row_a']}, col={meta['col_a']})")
    print(f"Cell B: pgid={meta['pgid_b']} (row={meta['row_b']}, col={meta['col_b']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
