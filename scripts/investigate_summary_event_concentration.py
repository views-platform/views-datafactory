#!/usr/bin/env python3
"""Which UCDP events are assigned to a cell-month their own metadata disowns?

Builds the catalog in ``reports/investigation_summary_event_concentration/``.
Raised by views-datafactory#533 (views-hydranet) extending #484: one
cell-month held 62% of a scored horizon's truth mass, collapsing the
effective sample size of that score to 2.58 cells.

Two independent mechanisms concentrate mass, and the first pass at this
question found only one of them, so both are measured here separately:

- **Temporal.** ``date_end_only`` assigns an annual-source event to its
  ``date_end`` month "regardless of whether the event spans multiple
  months" (its own docstring). A year-long aggregate lands on one month.
- **Spatial.** ``passthrough`` returns an event unchanged whatever its
  ``where_prec``, and the ``production_parity`` profile excludes only
  ``where_prec`` 4 and 6 -- so 5 (country-level) and 7 (unclear) are
  pinned to whatever single 0.5-degree cell their coordinates name.

Neither is a defect. Both reproduce VIEWSER ``GedLoader`` parity
deliberately, and every event involved carries honest UCDP precision
metadata. This script measures the consequence; it changes nothing and
recommends nothing.

Reads ``data/viewpoint/production_parity.parquet`` -- the distributed
event rows, one per (event, month), with survivorship and filtering
already applied. That file is the compiler's own input, which is why it
is the basis rather than the raw store: re-deriving survivorship here
would risk measuring something the pipeline does not actually see.

**Leverage is proxied by ``best``**, not measured on model scores. That
is sound for a count-unit CRPS, where a cell's contribution scales with
its magnitude, and views-hydranet reports the directly measured figure
is the same order -- but it is a proxy, and the effective sample sizes
below are computed on truth rather than on per-cell scores.

The two CSVs this writes are derived data and are deliberately not
committed; they regenerate in well under a minute. ``findings.md``
beside them is the durable record.

Usage::

    uv run python scripts/investigate_summary_event_concentration.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

VIEWPOINT = Path("data/viewpoint/production_parity.parquet")
OUT_DIR = Path("reports/investigation_summary_event_concentration")

#: UCDP ``type_of_violence`` -> the VIEWS feature-name infix.
TOV_NAMES = {1: "sb", 2: "ns", 3: "os"}

#: ``date_prec`` 4 is "within a month", 5 is "within a year or longer".
#: An event at 4 or coarser spanning >1 month cannot be resolved to the
#: single month it is assigned to.
COARSE_DATE_PREC = 4

#: ``where_prec`` 5 is "country level only", 7 is "unclear". Below 5 the
#: event is at least ADM2-resolved; 4 and 6 are already excluded by the
#: profile, so 5 and 7 are what reach a cell unresolved.
COARSE_WHERE_PREC = 5

#: VIEWS month_id epoch: ``month_id = (year - 1980) * 12 + month``,
#: January 1980 = 1. Mirrors ``VIEWS_EPOCH_YEAR`` in
#: ``datafactory_provenance.constants``; stated locally because this
#: script must keep working against an archived parquet.
EPOCH_YEAR = 1980

#: PRIO-GRID is a 720x360 half-degree lattice, gid 1 at (-90, -180).
GRID_COLS = 720
CELL_DEG = 0.5

COLUMNS = [
    "id", "best", "date_start", "date_end", "date_prec", "where_prec",
    "priogrid_gid", "type_of_violence", "date_month", "country",
    "conflict_name", "side_a", "side_b", "where_description",
]


def month_id_to_ym(month_id: int) -> str:
    """Render a VIEWS month_id as ``YYYY-MM``."""
    year = EPOCH_YEAR + (month_id - 1) // 12
    month = (month_id - 1) % 12 + 1
    return f"{year}-{month:02d}"


def effective_sample_size(values: np.ndarray) -> float:
    """Participation ratio ``(sum)^2 / sum(squares)``.

    Equals the element count when every element contributes equally, and
    1.0 when one element carries everything. This is views-hydranet's
    own instrument from #533, applied here per (violence type, month)
    slice over per-cell totals.
    """
    total = values.sum()
    if total <= 0:
        return float("nan")
    return float(total**2 / (values**2).sum())


def load_distributed_events(path: Path) -> pd.DataFrame:
    """Load the distributed event rows and derive the comparison fields."""
    df = pq.read_table(path, columns=COLUMNS).to_pandas()

    date_month = pd.to_datetime(df.date_month)
    df["month_id"] = (
        (date_month.dt.year - EPOCH_YEAR) * 12 + date_month.dt.month
    )
    start, end = pd.to_datetime(df.date_start), pd.to_datetime(df.date_end)
    df["span_months"] = (
        (end.dt.year - start.dt.year) * 12 + (end.dt.month - start.dt.month) + 1
    )
    df["tov"] = df.type_of_violence.map(TOV_NAMES)

    # One row per (event, month). An event spread across months appears
    # more than once, so this counts how many months it reached.
    df["n_rows"] = df.groupby("id").id.transform("size")

    df["lat"] = (
        -90 + ((df.priogrid_gid - 1) // GRID_COLS) * CELL_DEG + CELL_DEG / 2
    )
    df["lon"] = (
        -180 + ((df.priogrid_gid - 1) % GRID_COLS) * CELL_DEG + CELL_DEG / 2
    )
    return df


def flag_concentration(df: pd.DataFrame) -> pd.DataFrame:
    """Add the T / S concentration flags and the per-slice denominators."""
    # A feature column is (violence type, month, cell), so that is the
    # grain a cell-month total has to be taken at.
    cell_month = (
        df.groupby(["tov", "month_id", "priogrid_gid"], as_index=False)
        .best.sum().rename(columns={"best": "cm_total"})
    )
    df = df.merge(cell_month, on=["tov", "month_id", "priogrid_gid"], how="left")

    month = (
        df.groupby(["tov", "month_id"], as_index=False)
        .best.sum().rename(columns={"best": "mo_total"})
    )
    df = df.merge(month, on=["tov", "month_id"], how="left")

    df["temporal_conc"] = (
        (df.date_prec >= COARSE_DATE_PREC)
        & (df.span_months > 1)
        & (df.n_rows == 1)
    )
    df["spatial_conc"] = df.where_prec >= COARSE_WHERE_PREC
    df["concentrated"] = df.temporal_conc | df.spatial_conc

    df["flags"] = np.where(
        df.temporal_conc & df.spatial_conc, "T+S",
        np.where(df.temporal_conc, "T", np.where(df.spatial_conc, "S", "")),
    )
    df["ev_share_of_cm"] = df.best / df.cm_total
    df["cm_share_of_mo"] = df.cm_total / df.mo_total
    df["ym"] = df.month_id.map(month_id_to_ym)
    return df


def slice_effective_sample_sizes(df: pd.DataFrame) -> pd.DataFrame:
    """Per (violence type, month): ESS, and ESS with the top cell removed.

    The delta is the quantity that matters for #533: it says how much of
    a slice's score is one cell.
    """
    cell_month = df.groupby(
        ["tov", "month_id", "priogrid_gid"], as_index=False
    ).best.sum()

    rows = []
    for (tov, month_id), group in cell_month.groupby(["tov", "month_id"]):
        values = group.best.to_numpy(dtype=float)
        values = values[values > 0]
        if len(values) < 2:
            continue
        without_top = np.sort(values)[:-1]
        ess = effective_sample_size(values)
        ess_excl = (
            effective_sample_size(without_top) if len(without_top) >= 2
            else float("nan")
        )
        top = group.loc[group.best.idxmax()]
        rows.append(
            {
                "tov": tov,
                "month_id": month_id,
                "ym": month_id_to_ym(month_id),
                "n_cells": len(values),
                "mass": int(values.sum()),
                "ess": ess,
                "ess_excl_top": ess_excl,
                "ratio": ess_excl / ess if ess else float("nan"),
                "top_pgid": int(top.priogrid_gid),
                "top_val": int(top.best),
                "top_share": float(top.best / values.sum()),
            }
        )
    return pd.DataFrame(rows)


def report_scope(df: pd.DataFrame) -> None:
    """Print the scope figures that answer #533's ask 3."""
    total = df.best.sum()
    print(f"basis            : {VIEWPOINT}")
    print(f"rows             : {len(df)}   unique events: {df.id.nunique()}")
    print(f"date_month range : {df.date_month.min()} .. {df.date_month.max()}")
    n_spread = df.loc[df.n_rows > 1, "id"].nunique()
    print(f"events ever spread across months: {n_spread}")
    print()

    print("=== events by concentration mechanism ===")
    masks = {
        "all events": pd.Series(True, index=df.index),
        "temporal (T)": df.temporal_conc,
        "spatial (S)": df.spatial_conc,
        "both (T+S)": df.temporal_conc & df.spatial_conc,
        "either": df.concentrated,
    }
    for label, mask in masks.items():
        sub = df[mask]
        print(
            f"  {label:14s} n={len(sub):7d}  mass={sub.best.sum():9d}"
            f"  share={100 * sub.best.sum() / total:6.2f}%"
        )

    print()
    print("=== cell-months ===")
    cm_all = df.groupby(["tov", "month_id", "priogrid_gid"]).best.sum()
    cm_conc = (
        df[df.concentrated]
        .groupby(["tov", "month_id", "priogrid_gid"]).best.sum()
    )
    touched_mass = cm_all.reindex(cm_conc.index).sum()
    print(f"  total                  : {len(cm_all):7d}")
    print(
        f"  containing conc. mass  : {len(cm_conc):7d}"
        f"  ({100 * len(cm_conc) / len(cm_all):.2f}%)"
    )
    print(
        f"  mass in those          : {touched_mass:9d}"
        f"  ({100 * touched_mass / total:.2f}% of all mass)"
    )

    print()
    print("=== ceil_split non-conservation ===")
    per_event = df.drop_duplicates("id").best.sum()
    print(
        f"  mass over rows {total} - over events {per_event}"
        f" = {total - per_event} ({100 * (total - per_event) / total:.2f}%)"
    )

    print()
    print("=== concentrated share of mass, by half-decade ===")
    period = (EPOCH_YEAR + (df.month_id - 1) // 12) // 5 * 5
    by = pd.DataFrame(
        {
            "conc": df[df.concentrated].groupby(period[df.concentrated]).best.sum(),
            "all": df.groupby(period).best.sum(),
        }
    ).fillna(0)
    by["share"] = 100 * by.conc / by["all"]
    for p, row in by.iterrows():
        print(
            f"  {int(p)}-{int(p) + 4}: {int(row.conc):9d} / {int(row['all']):9d}"
            f"  = {row.share:5.1f}%"
        )


def report_tiers(conc: pd.DataFrame, ess: pd.DataFrame) -> None:
    """Print Tier A (cell-months), Tier B (cells) and Tier C (conflicts)."""
    print()
    print("=== Tier A: top concentrated events by mass ===")
    cols = [
        "id", "best", "ym", "month_id", "priogrid_gid", "lat", "lon", "tov",
        "flags", "date_prec", "where_prec", "span_months", "cm_total",
        "cm_share_of_mo", "country", "conflict_name",
    ]
    print(conc.nlargest(15, "best")[cols].to_string(index=False))

    print()
    print("=== Tier A: slices where one cell is the score ===")
    conc_cells = set(
        map(tuple, conc[["tov", "month_id", "priogrid_gid"]]
            .drop_duplicates().itertuples(index=False, name=None))
    )
    ess = ess.copy()
    ess["top_is_conc"] = [
        (r.tov, r.month_id, r.top_pgid) in conc_cells for r in ess.itertuples()
    ]
    worst = ess[(ess.mass >= 500) & ess.top_is_conc].nlargest(15, "ratio")
    print(worst[
        ["ym", "month_id", "tov", "n_cells", "mass", "ess", "ess_excl_top",
         "ratio", "top_pgid", "top_val", "top_share"]
    ].to_string(index=False))

    print()
    print("=== Tier B: repeat-offender cells ===")
    cells = (
        conc.groupby("priogrid_gid")
        .agg(
            conc_mass=("best", "sum"),
            n_events=("id", "size"),
            n_months=("month_id", "nunique"),
            lat=("lat", "first"),
            lon=("lon", "first"),
            countries=("country", lambda s: "/".join(sorted(set(s))[:2])),
        )
        .nlargest(12, "conc_mass")
    )
    print(cells.to_string())

    print()
    print("=== Tier C: by conflict ===")
    conflicts = (
        conc.groupby(["country", "conflict_name"])
        .agg(
            conc_mass=("best", "sum"),
            n=("id", "size"),
            first=("month_id", lambda s: month_id_to_ym(s.min())),
            last=("month_id", lambda s: month_id_to_ym(s.max())),
        )
        .nlargest(12, "conc_mass")
    )
    print(conflicts.to_string())


def write_catalog(conc: pd.DataFrame, ess: pd.DataFrame, out_dir: Path) -> None:
    """Write the two machine-readable catalog files."""
    out_dir.mkdir(parents=True, exist_ok=True)

    event_cols = [
        "id", "best", "ym", "month_id", "priogrid_gid", "lat", "lon", "tov",
        "flags", "date_prec", "where_prec", "span_months", "date_start",
        "date_end", "cm_total", "ev_share_of_cm", "cm_share_of_mo", "country",
        "conflict_name", "side_a", "side_b", "where_description",
    ]
    events_path = out_dir / "catalog_concentrated_events.csv"
    conc[event_cols].sort_values("best", ascending=False).to_csv(
        events_path, index=False
    )

    cell_months = (
        conc.groupby(["tov", "month_id", "priogrid_gid"], as_index=False)
        .agg(
            conc_mass=("best", "sum"),
            n_conc_events=("id", "size"),
            cm_total=("cm_total", "first"),
            cm_share_of_mo=("cm_share_of_mo", "first"),
            lat=("lat", "first"),
            lon=("lon", "first"),
            country=("country", "first"),
            conflict=("conflict_name", "first"),
            max_date_prec=("date_prec", "max"),
            max_where_prec=("where_prec", "max"),
        )
        .merge(
            ess[["tov", "month_id", "ess", "ess_excl_top", "ratio",
                 "top_pgid", "top_val"]],
            on=["tov", "month_id"], how="left",
        )
    )
    cell_months["slice_top_is_this_cell"] = (
        cell_months.top_pgid == cell_months.priogrid_gid
    )
    cell_months["ym"] = cell_months.month_id.map(month_id_to_ym)
    cell_months["conc_share_of_cm"] = (
        cell_months.conc_mass / cell_months.cm_total
    )
    cm_path = out_dir / "catalog_severe_cell_months.csv"
    cell_months.sort_values("conc_mass", ascending=False).to_csv(
        cm_path, index=False
    )

    print()
    print(f"[wrote] {events_path}  rows={len(conc)}")
    print(f"[wrote] {cm_path}  rows={len(cell_months)}")

    print()
    print("=== severity bands (cell-months by concentrated mass) ===")
    for floor in (10_000, 1_000, 100, 10, 1):
        band = cell_months[cell_months.conc_mass >= floor]
        print(
            f"  >= {floor:6d}: {len(band):6d} cell-months,"
            f" {int(band.conc_mass.sum()):9d} mass"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewpoint", type=Path, default=VIEWPOINT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    if not args.viewpoint.exists():
        print(f"ERROR: {args.viewpoint} not found. Build it with "
              f"scripts/build_viewpoint.py --profile production_parity")
        return 1

    df = flag_concentration(load_distributed_events(args.viewpoint))
    ess = slice_effective_sample_sizes(df)
    conc = df[df.concentrated].copy()

    report_scope(df)
    report_tiers(conc, ess)
    write_catalog(conc, ess, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
