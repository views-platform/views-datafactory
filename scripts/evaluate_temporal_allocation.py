#!/usr/bin/env python3
"""Does activity-weighted temporal allocation beat uniform?

Tier 2 of the allocator spec
(``reports/2026-11-04_summary_event_allocation_dossier/11_allocator_spec.md``),
run **before** T2 is implemented, because T2 needs a signature change
across five registered strategies and that churn is only earned if the
extra assumption pays.

THE TEST. Take events whose month we actually know -- ``date_prec <= 2``
and ``where_prec <= 2`` -- and coarsen them: pretend UCDP had only told us
the year. Allocate the event's total across that year's twelve months by
each candidate weight function, then score how much mass landed in the
month it really belonged to.

Ground truth is ``where_prec <= 2`` rather than ``<= 3`` deliberately.
``where_prec == 3`` is an admin-2 **centroid** assignment, so it is
precisely *coded* rather than precisely *known*; 13.7% of admin-2 units
span more than four of our cells. Scoring against contaminated truth
would flatter whatever we build. (Simon's call, 2026-11-05.)

LEAKAGE. The activity indicator is built from *other* events only -- the
event under test is removed from its own indicator. Without that the test
is circular and activity weighting would win by construction.

METRICS, per event:
  - ``hit`` share of the total that landed in the true month (1.0 is
    perfect, 1/12 is what uniform gets on average)
  - ``dist`` mass-weighted mean absolute distance in months from the true
    month (0.0 is perfect) -- an earth-mover distance on a line

.. warning::

   **Every number this script prints describes the allocator's decision,
   not what a consumer receives.** It scores rows as the allocation
   emits them. Whether those rows survive compilation is a separate
   question, and on the spatial axis the answer was *no* for every
   release up to v1.18.1: the compiler re-derived each event's cell from
   ``latitude``/``longitude`` and ignored the ``priogrid_gid`` the
   allocator had written (#547, C-368).

   The delivered layer is read by
   ``scripts/measure_allocation_delivery.py``, which goes through
   ``datafactory_query.load_dataset`` -- the consumer entry point. Grade
   a release there, not here.

   The temporal axis this script measures was never affected: the
   compiler reads the month field *by name*, so a month the allocator
   chose is a month the grid receives. That asymmetry is exactly why the
   distinction has to be stated rather than assumed -- the same script
   can be sound about one axis and silent about the other.

   Note also that ``priogrid_gid`` appears in ``load`` only as a
   validity filter (``>= 1``); no metric here is grouped by cell, so
   "report the delivered cell instead" is not available to this script
   and would not mean anything if it were. Issue #553 asked for that
   conversion first and the ask was wrong on inspection.

Usage::

    uv run python scripts/evaluate_temporal_allocation.py [--sample N]
"""

from __future__ import annotations

import argparse
import collections
import random
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from datafactory_viewpoint.apportionment import apportion

STORE = Path("data/consolidated/ucdp_store.parquet")

#: Ground truth: the month is known, and the place is known to <=25km.
TRUTH_DATE_PREC = 2
TRUTH_WHERE_PREC = 2

#: The indicator pool: well-located, well-dated events only.
EPOCH_YEAR = 1980


def _month_id(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    return (dt.dt.year - EPOCH_YEAR) * 12 + dt.dt.month


def load(store: Path) -> pd.DataFrame:
    df = pq.read_table(
        store,
        columns=[
            "id", "best", "date_prec", "where_prec", "date_start",
            "priogrid_gid", "type_of_violence", "dyad_new_id",
            "conflict_new_id", "side_b_new_id", "country_id",
        ],
    ).to_pandas()
    df = df[
        (df.priogrid_gid >= 1) & (df.type_of_violence < 4)
    ].drop_duplicates("id")
    df["month_id"] = _month_id(df.date_start)
    df["year"] = EPOCH_YEAR + (df.month_id - 1) // 12
    return df.dropna(subset=["month_id"])


def build_indicator(
    pool: pd.DataFrame, key: str
) -> dict[tuple[object, int], float]:
    """Activity by (key value, month) over the well-observed pool."""
    grouped = pool.groupby([key, "month_id"]).best.sum()
    return {k: float(v) for k, v in grouped.to_dict().items()}


def score(
    alloc: dict[int, int], true_month: int, total: int
) -> tuple[float, float]:
    if total <= 0:
        return (float("nan"), float("nan"))
    hit = alloc.get(true_month, 0) / total
    dist = sum(v * abs(m - true_month) for m, v in alloc.items()) / total
    return (hit, dist)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--sample", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20261105)
    args = ap.parse_args()

    if not args.store.exists():
        print(f"ERROR: {args.store} not found")
        return 1

    df = load(args.store)
    truth = df[
        (df.date_prec <= TRUTH_DATE_PREC)
        & (df.where_prec <= TRUTH_WHERE_PREC)
        & (df.best > 0)
    ]
    print(f"store events              : {len(df):,}")
    print(f"ground-truth pool         : {len(truth):,} "
          f"(date_prec<={TRUTH_DATE_PREC}, where_prec<={TRUTH_WHERE_PREC}, best>0)")
    print(f"their mass                : {int(truth.best.sum()):,}")

    keys = ["dyad_new_id", "conflict_new_id", "side_b_new_id", "country_id"]
    indicators = {k: build_indicator(truth, k) for k in keys}

    rng = random.Random(args.seed)
    idx = list(truth.index)
    if len(idx) > args.sample:
        idx = rng.sample(idx, args.sample)
    tested = truth.loc[idx]
    print(f"testing on                : {len(tested):,} coarsened events")
    print()

    results: dict[str, list] = collections.defaultdict(list)
    cascade_used: collections.Counter = collections.Counter()

    for row in tested.itertuples():
        year_start = (row.year - EPOCH_YEAR) * 12 + 1
        months = list(range(year_start, year_start + 12))
        total = int(row.best)

        # --- T1 uniform -------------------------------------------------
        uni = apportion(total, dict.fromkeys(months, 1.0))
        results["T1_uniform"].append(score(uni, row.month_id, total))

        # --- T2 activity, leakage-free cascade --------------------------
        chosen = None
        for key in keys:
            kv = getattr(row, key)
            table = indicators[key]
            w = {}
            for m in months:
                activity = table.get((kv, m), 0.0)
                # remove the event under test from its own indicator
                if m == row.month_id:
                    activity -= total
                w[m] = max(activity, 0.0)
            if sum(w.values()) > 0:
                chosen = (key, w)
                break
        if chosen is None:
            cascade_used["uniform_fallback"] += 1
            act = uni
        else:
            cascade_used[chosen[0]] += 1
            act = apportion(total, chosen[1])
        results["T2_activity"].append(score(act, row.month_id, total))

        # --- T0 endpoint (parity control): all on the last month --------
        end = dict.fromkeys(months, 0)
        end[months[-1]] = total
        results["T0_endpoint"].append(score(end, row.month_id, total))

    print("=== cascade level actually used (leakage-free) ===")
    for k, v in cascade_used.most_common():
        print(f"  {k:18s} {v:>7,}  ({100*v/len(tested):5.1f}%)")
    print()
    print("=== results: higher hit is better, lower dist is better ===")
    print(f"  {'strategy':14s} {'hit (mean)':>12s} {'hit (median)':>13s} "
          f"{'dist months':>13s} {'dist median':>12s}")
    for name in ("T0_endpoint", "T1_uniform", "T2_activity"):
        arr = np.array(results[name], dtype=float)
        arr = arr[~np.isnan(arr).any(axis=1)]
        print(f"  {name:14s} {arr[:,0].mean():>12.4f} "
              f"{np.median(arr[:,0]):>13.4f} {arr[:,1].mean():>13.3f} "
              f"{np.median(arr[:,1]):>12.3f}")
    print()
    uni_all = np.array(results["T1_uniform"], dtype=float)
    act_all = np.array(results["T2_activity"], dtype=float)
    ok = ~(np.isnan(uni_all).any(axis=1) | np.isnan(act_all).any(axis=1))
    u, act = uni_all[ok], act_all[ok]
    better = float((act[:, 1] < u[:, 1]).mean())
    worse = float((act[:, 1] > u[:, 1]).mean())
    print("=== does activity beat uniform? (paired, same events) ===")
    print(f"  activity closer than uniform : {100*better:5.1f}% of events")
    print(f"  activity further than uniform: {100*worse:5.1f}%")
    print(f"  tied                         : {100*(1-better-worse):5.1f}%")
    du, da = float(u[:, 1].mean()), float(act[:, 1].mean())
    hu, ha = float(u[:, 0].mean()), float(act[:, 0].mean())
    print(
        f"  mean distance   uniform {du:.3f} -> activity {da:.3f}"
        f"  ({100*(du-da)/du:+.1f}%)"
    )
    print(
        f"  mean hit share  uniform {hu:.4f} -> activity {ha:.4f}"
        f"  ({100*(ha-hu)/hu:+.1f}%)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
