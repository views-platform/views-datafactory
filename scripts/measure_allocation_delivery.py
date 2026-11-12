"""Measure how much allocated fatality mass is delivered to the wrong cell.

The UCDP spatial allocator records its decision by rewriting ``priogrid_gid``
and leaves ``latitude``/``longitude`` at the source centroid. The event
compiler never reads ``priogrid_gid`` -- ``grid_compilation._place_events``
derives the cell with ``latlon_to_pgid(lat, lon)``. So the allocator's
decision is discarded, and every allocated row is delivered to the cell it
came from.

This script quantifies that. It reads a built viewpoint parquet and, for
every row, compares the cell the row *declares* against the cell the
compiler *would compute*. It does not need a compiled grid: the compiler's
placement rule is one function call, so applying it here reproduces the
delivered cell exactly.

Three quantities, deliberately kept apart because they are routinely
conflated:

**eligible** mass
    Everything the allocator is entitled to move (``where_prec >= 4``).

**allocated** mass
    Rows the allocator actually emitted as a distribution, i.e. where the
    declared cell differs from the source event's own cell.

**displaced** mass
    Mass whose *delivered* cell differs from its *declared* cell. This is
    the defect's size. An allocation that happens to land back on its own
    source cell is eligible and allocated but not displaced.

Run after ``scripts/build_viewpoint.py --profile kgi_kti_activity``.
Read-only with respect to the data; writes nothing.

**Three modes, because the delivered layer cannot answer every question
and pretending otherwise is how this defect was missed.**

``--source`` only (default)
    Reports what the allocator decided and what a coordinate-derived
    compile would deliver instead. This is the pre-fix diagnosis.

``--compiled DIR``
    **Exact reconciliation.** Aggregates the viewpoint by (declared
    cell, month) and compares it against a grid compiled from that same
    viewpoint. Both sides are the same quantity, so a correct compiler
    matches to the unit. This is the proof that the code is right.

``--served URL``
    Reads the served store through ``datafactory_query.load_dataset``
    -- the consumer entry point, the same function a model's dataloader
    calls. **Bounds, not equalities:** production harvests fresher data
    than any local build, so served figures drift by a percent or so.
    This is the proof that the fix reached a consumer.

The served grid holds cell-month aggregates and carries **no event
ids**, so per-event questions ("how many cells does event 463131
occupy?") cannot be asked of it directly. Reconciliation is the
instrument that answers them at the delivered layer: if every
(cell, month) total matches what the viewpoint predicts, then every
event's footprint was delivered as allocated.

Opened for #548, extended for #553 (epic #547).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from datafactory_priogrid.cell_generator import latlon_to_pgid
from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG

logger = logging.getLogger(__name__)

#: The Tigray war summary event -- 113,368 deaths, ``where_prec=5``,
#: ``date_prec=5``, Jan-Dec 2021, ``where_description="Tigray, Afar,
#: Amhara"``. The event this epic was opened for.
TIGRAY_EVENT_ID = 463131

#: Its regional centroid cell, which held 113,395 state-based fatalities in
#: a single month before v1.18.0.
TIGRAY_PGID = 148759

#: The second summary event -- 121,848 deaths, Aug-Oct 2022. Included
#: because activity weighting moves its mass into August, which is why
#: August overtook December as the largest month (ADR-053 amendment 4).
SECOND_EVENT_ID = 463137

#: Columns the measurement needs. Read explicitly rather than loading the
#: whole table: the production parquet is 2.65M rows wide.
_COLUMNS = (
    "id",
    "where_prec",
    "priogrid_gid",
    "latitude",
    "longitude",
    "best",
    "type_of_violence",
    "date_month",
)


def _fmt(n: float) -> str:
    return f"{n:,.0f}"


def _pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.2f}%" if whole else "n/a"


def load(path: Path) -> dict[str, np.ndarray]:
    """Read the measurement columns from a viewpoint parquet."""
    table = pq.read_table(path, columns=list(_COLUMNS))
    logger.info("read %s rows from %s", f"{table.num_rows:,}", path)
    cols = {
        name: np.asarray(table.column(name).to_pylist())
        for name in ("id", "date_month")
    }
    for name in ("where_prec", "priogrid_gid", "type_of_violence"):
        raw = table.column(name).to_pylist()
        cols[name] = np.array(
            [-1 if v is None else int(v) for v in raw], dtype="int64"
        )
    for name in ("latitude", "longitude", "best"):
        raw = table.column(name).to_pylist()
        cols[name] = np.array(
            [np.nan if v is None else float(v) for v in raw],
            dtype="float64",
        )
    return cols


def delivered_pgid(cols: dict[str, np.ndarray]) -> np.ndarray:
    """The cell the compiler would place each row in.

    This is ``_place_events``' rule, applied here rather than inferred.
    Rows with no usable coordinates are marked ``-1``; the compiler counts
    those as ``n_skipped_spatial``.
    """
    lat, lon = cols["latitude"], cols["longitude"]
    # latlon_to_pgid RAISES on an out-of-range coordinate rather than
    # returning a sentinel, and it is called here on the whole vector --
    # so one row at latitude 90.0 would abort the entire measurement
    # with "Latitude out of range" instead of reporting. The compiler
    # catches per row; this must not be less tolerant than the thing it
    # is measuring.
    usable = (
        np.isfinite(lat) & np.isfinite(lon)
        & (lat >= -90.0) & (lat <= 90.0)
        & (lon >= -180.0) & (lon <= 180.0)
    )
    out = np.full(lat.shape, -1, dtype="int64")
    if usable.any():
        out[usable] = latlon_to_pgid(
            lat[usable], lon[usable], DEFAULT_GRID_CONFIG
        ).astype("int64")
    n_unusable = int((~usable).sum())
    if n_unusable:
        logger.warning(
            "%d rows have coordinates outside the grid; counted as "
            "unplaceable rather than aborting the measurement",
            n_unusable,
        )
    return out


def report_totals(cols: dict[str, np.ndarray], got: np.ndarray) -> None:
    """Eligible, allocated and displaced mass, split by precision."""
    best = cols["best"]
    declared = cols["priogrid_gid"]
    wp = cols["where_prec"]
    total = np.nansum(best)

    eligible = wp >= 4
    displaced = (got != declared) & (got != -1)

    print("=" * 72)
    print("TOTALS")
    print("=" * 72)
    print(f"rows                       : {len(best):,}")
    print(f"total best                 : {_fmt(total)}")
    print(
        f"eligible (where_prec >= 4) : {_fmt(np.nansum(best[eligible]))} "
        f"({_pct(np.nansum(best[eligible]), total)}) "
        f"across {int(eligible.sum()):,} rows"
    )
    print(
        f"DISPLACED                  : {_fmt(np.nansum(best[displaced]))} "
        f"({_pct(np.nansum(best[displaced]), total)}) "
        f"across {int(displaced.sum()):,} rows"
    )
    print(
        f"  distinct events displaced: "
        f"{len(set(cols['id'][displaced].tolist())):,}"
    )

    print("\nby where_prec:")
    print(f"  {'wp':>4} {'rows':>10} {'eligible best':>16} "
          f"{'displaced best':>16} {'displaced %':>12}")
    for code in sorted(set(wp.tolist())):
        at = wp == code
        d = at & displaced
        e_mass = np.nansum(best[at])
        d_mass = np.nansum(best[d])
        print(
            f"  {code:>4} {int(at.sum()):>10,} {_fmt(e_mass):>16} "
            f"{_fmt(d_mass):>16} {_pct(d_mass, e_mass):>12}"
        )

    print("\nby type_of_violence (displaced only):")
    for tv in sorted(set(cols["type_of_violence"].tolist())):
        d = displaced & (cols["type_of_violence"] == tv)
        if d.any():
            print(f"  tv={tv}: {_fmt(np.nansum(best[d]))} deaths "
                  f"across {int(d.sum()):,} rows")


def report_event(
    cols: dict[str, np.ndarray], got: np.ndarray, event_id: int
) -> None:
    """Allocated vs delivered footprint for one event."""
    at = cols["id"] == event_id
    if not at.any():
        print(f"\nevent {event_id}: NOT PRESENT in this viewpoint")
        return

    best = cols["best"][at]
    declared = cols["priogrid_gid"][at]
    got_at = got[at]
    months = cols["date_month"][at]

    print("=" * 72)
    print(f"EVENT {event_id}")
    print("=" * 72)
    print(f"rows                 : {int(at.sum()):,}")
    print(f"sum best             : {_fmt(np.nansum(best))}")
    print(f"where_prec           : {sorted(set(cols['where_prec'][at]))}")
    print(f"allocated cells      : {len(set(declared.tolist()))}")
    print(f"DELIVERED cells      : {len(set(got_at.tolist()))}")
    print(f"months               : {len(set(months.tolist()))}")

    # Worst cell-month, delivered. Not the worst month of one cell: the
    # worst (cell, month) pair anywhere in the event's span. Checking a
    # single pre-chosen month is what flattered the 2026-11-11 verdict by
    # a factor of 18.
    for label, cell in (("allocated", declared), ("delivered", got_at)):
        acc: dict[tuple[int, str], float] = {}
        for c, m, v in zip(cell, months, best, strict=True):
            if np.isfinite(v):
                acc[(int(c), str(m))] = acc.get((int(c), str(m)), 0.0) + v
        worst = max(acc.items(), key=lambda kv: kv[1])
        print(
            f"worst {label} cell-month: {_fmt(worst[1])} "
            f"at cell {worst[0][0]}, {worst[0][1]}"
        )


def reconcile_against_compiled(
    cols: dict[str, np.ndarray], compiled_dir: Path
) -> bool:
    """Compare viewpoint-predicted cell-months against a compiled grid.

    The viewpoint declares, per row, a cell and a month. Summing ``best``
    over (declared cell, month) is therefore a prediction of exactly what
    the compiler should write. A compiler that honours the declaration
    reproduces it to the unit; one that re-derives the cell from
    coordinates does not.

    Both sides are the same quantity on the same data, so this is an
    equality rather than a bound -- which is what makes it the proof
    that the code is right, as distinct from the served-store read,
    which can only be a bound.

    Returns True when they reconcile.
    """
    grid_path = compiled_dir / "grid.npy"
    names_path = compiled_dir / "feature_names.json"
    if not grid_path.exists() or not names_path.exists():
        print(f"\nno compiled grid at {compiled_dir} -- skipping "
              f"reconciliation (and a skip is not a pass)")
        return False

    import json

    names = json.loads(names_path.read_text())
    try:
        feat = names.index("ged_sb_best")
    except ValueError:
        print(f"\nged_sb_best not in {names_path} -- cannot reconcile")
        return False

    grid = np.load(grid_path, mmap_mode="r")
    slab = np.asarray(grid[..., feat])  # [T, NROW, NCOL]
    n_t, n_row, n_col = slab.shape

    # Predicted: state-based rows, grouped by declared cell and month.
    sb = cols["type_of_violence"] == 1
    predicted: dict[tuple[int, str], float] = {}
    for pgid, month, best in zip(
        cols["priogrid_gid"][sb], cols["date_month"][sb],
        cols["best"][sb], strict=True,
    ):
        if np.isfinite(best) and pgid >= 1:
            key = (int(pgid), str(month))
            predicted[key] = predicted.get(key, 0.0) + float(best)

    # Delivered: the same grouping, read off the grid.
    start_year = _compiled_start_year(compiled_dir)
    mismatched = 0
    worst = (0.0, None)
    checked = 0
    for (pgid, month), want in predicted.items():
        t = _month_index(month, start_year)
        if t is None or t >= n_t:
            continue
        row, col = divmod(pgid - 1, n_col)
        if row >= n_row:
            continue
        got = float(slab[t, row, col])
        checked += 1
        # The grid aggregates every event in that cell-month, so the
        # delivered value is >= this event-group's share. Equality holds
        # only when the prediction covers all contributors -- which it
        # does, because `predicted` is built from the whole viewpoint.
        #
        # Written as `not (<= tol)` rather than `> tol` on purpose: every
        # comparison against NaN is False, so `got - want > 0.5` would
        # treat a NaN delivered value as an exact match. A null `best`
        # aggregated by sum_field reaches the grid as NaN, so this is
        # reachable, not theoretical.
        if not (abs(got - want) <= 0.5):
            mismatched += 1
            if abs(got - want) > abs(worst[0]):
                worst = (got - want, (pgid, month, want, got))

    print("\n" + "=" * 72)
    print("RECONCILIATION: viewpoint prediction vs compiled grid")
    print("=" * 72)
    print(f"cell-months predicted : {len(predicted):,}")
    print(f"cell-months checked   : {checked:,}")
    print(f"mismatched            : {mismatched:,}")

    # A grid whose temporal range does not cover the viewpoint sends
    # every key down the `continue` path, leaving checked == 0 and
    # mismatched == 0 -- which would print "delivered exactly" and exit
    # 0 having compared nothing. Same shape as the missing-grid case
    # above, which was handled; this one was not.
    skipped = len(predicted) - checked
    if checked == 0:
        print("\n  NOTHING WAS CHECKED. The compiled grid's temporal "
              "range does not overlap the viewpoint, so this "
              "reconciliation is not a result.")
        return False
    if skipped:
        print(f"\n  {skipped:,} predicted cell-months fell outside the "
              f"grid's range and were NOT checked. A partial "
              f"reconciliation is not a pass.")
        return False
    if mismatched:
        d, detail = worst
        print(f"worst discrepancy     : {d:+,.0f}  at {detail}")
        print("\n  DELIVERY DOES NOT REPRODUCE THE ALLOCATION.")
    else:
        print("\n  every predicted cell-month was delivered exactly.")
    return mismatched == 0


def _compiled_start_year(compiled_dir: Path) -> int:
    """Read the compiled grid's first month, falling back to 1989."""
    import json

    steps = compiled_dir / "time_steps.npy"
    if steps.exists():
        first = np.load(steps, allow_pickle=False)[0]
        return int(str(np.datetime64(first, "Y")))
    meta = compiled_dir / "metadata.json"
    if meta.exists():
        return int(json.loads(meta.read_text()).get("start_year", 1989))
    return 1989


def _month_index(month: str, start_year: int) -> int | None:
    """Months since January of start_year, or None if unparseable."""
    try:
        year, mon = int(month[:4]), int(month[5:7])
    except (ValueError, IndexError):
        return None
    idx = (year - start_year) * 12 + (mon - 1)
    return idx if idx >= 0 else None


def report_served(url: str) -> None:
    """Read the delivered month-504 slice through the consumer entry point.

    Bounds, not equalities: production harvests fresher data than any
    local build. Read through ``load_dataset`` deliberately -- it is the
    function a model's dataloader calls, and the whole lesson of #547 is
    that a number measured anywhere else is not evidence about what a
    consumer receives.
    """
    from datafactory_query import load_dataset

    print("\n" + "=" * 72)
    print(f"SERVED STORE: {url}")
    print("=" * 72)

    df = load_dataset(
        region="global", start=504, end=504,
        features=["ged_sb_best"], output_format="dataframe",
        data_dir=url,
    ).reset_index()
    v = df["ged_sb_best"].to_numpy(dtype="float64")
    pg = df["priogrid_id"].to_numpy()

    tig = float(v[pg == TIGRAY_PGID][0])
    i = int(np.nanargmax(v))
    tot = float(np.nansum(v))
    ess = tot ** 2 / float(np.nansum(v ** 2))
    print("month 504 (2021-12), state-based:")
    print(f"  cell {TIGRAY_PGID}        : {_fmt(tig):>12}   "
          f"criterion < 1,000")
    print(f"  largest cell          : {_fmt(float(v[i])):>12}   "
          f"criterion < 5,000   (pgid {pg[i]})")
    print(f"  its share of the slice: {100*v[i]/tot:11.2f}%   "
          f"criterion < 25%")
    print(f"  slice ESS             : {ess:12.2f}   criterion > 10")
    print(f"  cells with mass       : {int(np.sum(v > 0)):>12,}   "
          f"criterion > 100")

    # The event's whole span, which is the row a single month flattered.
    df21 = load_dataset(
        region="global", start=493, end=504,
        features=["ged_sb_best"], output_format="dataframe",
        data_dir=url,
    ).reset_index()
    at = df21[df21.priogrid_id == TIGRAY_PGID].sort_values("month_id")
    print(f"\ncell {TIGRAY_PGID} across 2021 "
          f"(the series a single month cannot show):")
    for _, r in at.iterrows():
        print(f"  month {int(r.month_id)}  {r.ged_sb_best:>12,.0f}")
    print(f"  12-month sum          : {at.ged_sb_best.sum():>12,.0f}")
    print(f"  worst cell-month      : {at.ged_sb_best.max():>12,.0f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/viewpoint/kgi_kti_activity.parquet"),
        help="built viewpoint parquet to measure",
    )
    parser.add_argument(
        "--compiled",
        type=Path,
        default=None,
        help=(
            "compiled grid directory to reconcile the viewpoint "
            "against, exactly (proves the compiler honours the "
            "declaration)"
        ),
    )
    parser.add_argument(
        "--served",
        default=None,
        help=(
            "served zarr store URL to read through load_dataset "
            "(proves the fix reached a consumer; bounds, not "
            "equalities -- production data is fresher)"
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.source.exists():
        raise SystemExit(
            f"{args.source} not found -- run "
            f"scripts/build_viewpoint.py --profile kgi_kti_activity first"
        )

    cols = load(args.source)
    got = delivered_pgid(cols)
    report_totals(cols, got)
    for event_id in (TIGRAY_EVENT_ID, SECOND_EVENT_ID):
        report_event(cols, got, event_id)

    reconciled = True
    if args.compiled is not None:
        reconciled = reconcile_against_compiled(cols, args.compiled)
    if args.served is not None:
        report_served(args.served)

    # A reconciliation that fails must not exit 0. Returning the boolean
    # and discarding it would make this script safe to wire into CI and
    # useless there -- the same fail-green shape the defect it measures
    # had. A missing compiled grid also returns False: a check that
    # could not run is not a check that passed.
    if not reconciled:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
