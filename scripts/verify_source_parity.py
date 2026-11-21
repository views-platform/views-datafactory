#!/usr/bin/env python3
"""Source parity — does what we serve equal what UCDP published?

Nothing else in this repository asks this question. Every other
check compares one of our stages to another of our stages, which is
why a four-and-a-half-month defect ran in production until an
external reader compared a number we had mailed him to the number on
ucdp.uu.se. Conservation invariants held throughout: deaths were
neither created nor destroyed by the pipeline, because the error
entered at ingestion of a release UCDP later withdrew, which is
upstream of everything conservation watches.

This script compares the **served grid** against the **annual UCDP
release in our own consolidated store**, per year and per violence
type. The annual release file *is* UCDP's published data, so no
network call to UCDP is made and no rate limit applies: the release
in our store is pinned, which also means this check is stationary.
Asserting equality against a third party's *current* web figure
would go red whenever UCDP revised its back catalogue, and a check
that goes red for reasons outside the repository trains its reader
to ignore it (C-320).

What a difference means
-----------------------
Our deliverable is not the annual release alone. ADR-015 records
that ``.9`` carries events present in no annual or candidate
release, so for a given year

    served  ==  annual release  +  the .9-exclusive mass

and a bare comparison against the release would show a positive
difference *by design*. This script therefore computes that
exclusive mass as well and reports the **unexplained** remainder.
Only the remainder is a finding.

A negative remainder means we serve fewer deaths than the source
published — a short harvest, a dropped release, a filter nobody
meant to apply. A positive remainder means we serve deaths the
source did not publish — the withdrawn-event defect's own
signature.

Usage::

    uv run python scripts/verify_source_parity.py
    uv run python scripts/verify_source_parity.py --zarr-url http://host/grid.zarr
    uv run python scripts/verify_source_parity.py --store path/to/ucdp_store.parquet
    uv run python scripts/verify_source_parity.py --json

Exit codes: 0 parity holds, 1 an unexplained difference, 2 the
check could not be run (no store, no annual release, no grid).
Requires ``~/.netrc`` credentials for the zarr server.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# month_id 1 is 1980-01, the VIEWS epoch. Stated once, used twice.
_MONTH_ID_EPOCH_YEAR = 1980

# UCDP's own coding. 4 exists in the data and is not delivered as a
# ged_* feature, so it is deliberately absent from this map and any
# year containing it would show up as an unexplained difference
# rather than being silently dropped.
_VIOLENCE_FEATURE = {
    1: "ged_sb_best",
    2: "ged_ns_best",
    3: "ged_os_best",
}


def months_of(year: int) -> tuple[int, int]:
    """The inclusive month_id range of a calendar year."""
    first = (year - _MONTH_ID_EPOCH_YEAR) * 12 + 1
    return first, first + 11


def latest_annual_version(store: Path) -> str:
    """The newest annual ``_source_version`` in the consolidated store.

    Raises if there is none: a store with no annual release cannot
    answer this question, and guessing from ``.9`` would compare the
    pipeline against itself.
    """
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    table = pq.read_table(store, columns=["_source_type", "_source_version"])
    annual = table.filter(pc.equal(table["_source_type"], "annual"))
    if annual.num_rows == 0:
        raise SystemExit(
            f"{store} holds no rows with _source_type == 'annual'. "
            "Source parity cannot be checked without the published "
            "release to check against."
        )
    versions = set(annual["_source_version"].to_pylist())
    # Version strings are "<major>.<minor>"; compare as integers so
    # 26.1 sorts above 25.11 rather than below it as text would.
    def key(v: str) -> tuple[int, ...]:
        return tuple(int(p) for p in v.split("."))

    newest: str = max(versions, key=key)
    return newest


def source_totals(store: Path, version: str) -> dict[tuple[int, int], float]:
    """``best`` per (year, type_of_violence) in one annual release.

    **Deduplicated by event id.** One ``_source_version`` can sit in
    the store under several harvest vintages — ADR-017's subject, a
    re-fetch of the same release — and summing the rows as they lie
    counts every event once per vintage. Measured on the local store
    on 2026-11-22: annual 25.1 held 769,836 rows for 384,918
    distinct ids, each exactly twice, from harvests on 2026-03-23
    and 2026-05-21. Summing naively doubled every published figure
    and the check reported 108 of 108 totals as failures.

    The later vintage wins, matching "latest ingestion is the
    truth" rather than averaging two readings of one release.
    """
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    table = pq.read_table(
        store,
        columns=["id", "best", "year", "type_of_violence",
                 "_source_type", "_source_version", "_ingested_at"],
    )
    rows = table.filter(
        pc.and_(
            pc.equal(table["_source_type"], "annual"),
            pc.equal(table["_source_version"], version),
        )
    ).sort_by([("_ingested_at", "ascending")])

    ids = rows["id"].to_pylist()
    best = rows["best"].to_pylist()
    years = rows["year"].to_pylist()
    tovs = rows["type_of_violence"].to_pylist()

    # Ascending ingestion order, so a later vintage overwrites.
    latest: dict[int, tuple[int, int, float]] = {}
    for i, b, y, t in zip(ids, best, years, tovs, strict=True):
        if i is None or b is None or y is None or t is None:
            continue
        latest[int(i)] = (int(y), int(t), float(b))

    totals: dict[tuple[int, int], float] = {}
    for year, tov, value in latest.values():
        totals[(year, tov)] = totals.get((year, tov), 0.0) + value
    return totals


def dot9_exclusive_totals(
    store: Path, annual_version: str,
) -> dict[tuple[int, int], float]:
    """``best`` per (year, tov) for ids in latest ``.9`` but not in the release.

    This is the mass ADR-015 records as legitimately ours and not
    UCDP's annual publication. Computed from the *latest* ``.9``
    version only, matching the viewpoint's own survivorship.
    """
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    table = pq.read_table(
        store,
        columns=["id", "best", "year", "type_of_violence",
                 "_source_type", "_source_version", "_ingested_at"],
    )
    annual = table.filter(
        pc.and_(
            pc.equal(table["_source_type"], "annual"),
            pc.equal(table["_source_version"], annual_version),
        )
    )
    annual_ids = set(annual["id"].to_pylist())

    dot9 = table.filter(pc.equal(table["_source_type"], "dot9"))
    if dot9.num_rows == 0:
        return {}
    versions = set(dot9["_source_version"].to_pylist())

    def key(v: str) -> tuple[int, ...]:
        return tuple(int(p) for p in v.split("."))

    newest = max(versions, key=key)
    latest = dot9.filter(pc.equal(dot9["_source_version"], newest))

    latest = latest.sort_by([("_ingested_at", "ascending")])
    ids = latest["id"].to_pylist()
    best = latest["best"].to_pylist()
    years = latest["year"].to_pylist()
    tovs = latest["type_of_violence"].to_pylist()

    # Deduplicated by id for the same reason source_totals is: one
    # .9 version can sit under several harvest vintages.
    newest_row: dict[int, tuple[int, int, float]] = {}
    for i, b, y, t in zip(ids, best, years, tovs, strict=True):
        if i is None or i in annual_ids or b is None or y is None or t is None:
            continue
        newest_row[int(i)] = (int(y), int(t), float(b))

    totals: dict[tuple[int, int], float] = {}
    for year, tov, value in newest_row.values():
        totals[(year, tov)] = totals.get((year, tov), 0.0) + value
    return totals


def served_totals(
    zarr_url: str | None, years: list[int],
) -> dict[tuple[int, int], float]:
    """``ged_*_best`` per (year, tov), read through the consumer entry point.

    Deliberately ``load_dataset`` and not a direct array read: the
    question is what a consumer receives, and a check that reads the
    store by a path no consumer uses can pass while consumers get
    nothing (C-313).
    """
    import numpy as np

    from datafactory_query import load_dataset

    kwargs: dict[str, Any] = {"region": "global"}
    if zarr_url is not None:
        kwargs["data_dir"] = zarr_url

    totals: dict[tuple[int, int], float] = {}
    for tov, feature in sorted(_VIOLENCE_FEATURE.items()):
        for year in years:
            start, end = months_of(year)
            frame = load_dataset(
                start=start, end=end, features=[feature], **kwargs,
            )
            totals[(year, tov)] = float(np.nansum(frame.values))
    return totals


def compare(
    served: dict[tuple[int, int], float],
    source: dict[tuple[int, int], float],
    exclusive: dict[tuple[int, int], float],
    tolerance: float,
) -> list[dict[str, Any]]:
    """One row per (year, tov), with the unexplained remainder."""
    keys = sorted(set(served) | set(source) | set(exclusive))
    rows = []
    for year, tov in keys:
        s = served.get((year, tov), 0.0)
        p = source.get((year, tov), 0.0)
        x = exclusive.get((year, tov), 0.0)
        remainder = s - (p + x)
        rows.append({
            "year": year,
            "type_of_violence": tov,
            "feature": _VIOLENCE_FEATURE.get(tov, f"<tov {tov}>"),
            "served": s,
            "published": p,
            "dot9_exclusive": x,
            "unexplained": remainder,
            "ok": abs(remainder) <= tolerance,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare served UCDP totals against the published release",
    )
    parser.add_argument(
        "--store", type=Path,
        default=Path("data/consolidated/ucdp_store.parquet"),
        help="consolidated UCDP store holding the annual release",
    )
    parser.add_argument(
        "--zarr-url", default=None,
        help="served zarr URL; omitted reads the local assembled grid",
    )
    parser.add_argument(
        "--tolerance", type=float, default=0.0,
        help="absolute deaths of unexplained difference tolerated per cell",
    )
    parser.add_argument(
        "--skip-last-year", action="store_true",
        help="exclude the newest year the release covers, which a "
             "mid-year release covers only partially",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable")
    args = parser.parse_args()

    if not args.store.exists():
        print(f"SKIP: no consolidated store at {args.store}", file=sys.stderr)
        return 2

    version = latest_annual_version(args.store)
    source = source_totals(args.store, version)
    if not source:
        print(f"SKIP: annual release {version} has no usable rows",
              file=sys.stderr)
        return 2
    exclusive = dot9_exclusive_totals(args.store, version)

    years = sorted({year for year, _ in source})
    if args.skip_last_year and len(years) > 1:
        years = years[:-1]

    served = served_totals(args.zarr_url, years)
    source = {k: v for k, v in source.items() if k[0] in years}
    exclusive = {k: v for k, v in exclusive.items() if k[0] in years}

    rows = compare(served, source, exclusive, args.tolerance)
    failures = [r for r in rows if not r["ok"]]

    if args.json:
        print(json.dumps(
            {"annual_version": version, "tolerance": args.tolerance,
             "rows": rows, "failures": len(failures)},
            indent=2,
        ))
    else:
        print(f"Source parity against UCDP annual release {version}")
        print(f"  served read through load_dataset"
              f"{' from ' + args.zarr_url if args.zarr_url else ' (local grid)'}")
        print()
        print(f"{'year':>6} {'feature':>14} {'served':>14} "
              f"{'published':>14} {'.9 excl':>12} {'unexplained':>13}")
        for r in rows:
            mark = "" if r["ok"] else "   <-- UNEXPLAINED"
            print(f"{r['year']:>6} {r['feature']:>14} {r['served']:>14,.0f} "
                  f"{r['published']:>14,.0f} {r['dot9_exclusive']:>12,.0f} "
                  f"{r['unexplained']:>+13,.0f}{mark}")
        print()
        if failures:
            print(f"FAIL: {len(failures)} of {len(rows)} year/violence-type "
                  f"totals differ from the published release by more than "
                  f"{args.tolerance:,.0f} deaths after accounting for "
                  f".9-exclusive events.")
            print("A negative remainder means we serve fewer deaths than "
                  "UCDP published. A positive one means we serve deaths it "
                  "did not. Neither is a threshold to move.")
        else:
            print(f"PASS: all {len(rows)} year/violence-type totals equal the "
                  f"published release once .9-exclusive events are counted.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
