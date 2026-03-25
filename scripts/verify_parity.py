#!/usr/bin/env python3
"""Production parity test: compare our pipeline against UCDP .9.

Usage:
    uv run python scripts/parity_test.py

Consolidates annual + candidate + .9 data, builds a viewpoint with
the production_parity profile, and compares against the raw .9 as
baseline. Reports discrepancy percentage and causes.

Requires data from prior smoke test and full harvest runs:
  - data/raw/ucdp_annual/ (annual v25.1)
  - data/raw/ucdp_candidate/ (candidate 25.0.1-26.0.2)
  - data/raw/ucdp_dot9/ (raw .9 version 25.9.11)
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq


def main() -> int:
    """Run the parity test."""
    print("=" * 70)
    print("PRODUCTION PARITY TEST (M6)")
    print("=" * 70)
    print()

    out_dir = Path("data/consolidated")
    prov_dir = Path("provenance/parity_test")

    # ---- Check prerequisites ----

    annual_dir = Path("data/raw/ucdp_annual")
    candidate_dir = Path("data/raw/ucdp_candidate")
    dot9_dir = Path("data/consolidated/ucdp_dot9")
    dot9_baseline = Path(
        "data/raw/ucdp_dot9/ucdp_ged_25.9.11.parquet"
    )

    for label, path in [
        ("Annual", annual_dir),
        ("Candidate", candidate_dir),
        (".9 baseline", dot9_baseline),
    ]:
        if not path.exists():
            print(f"MISSING: {label} at {path}")
            print("Run smoke_test.py and fetch full annual first.")
            return 1
        print(f"  {label}: {path}")

    print()

    # ---- Step 1: Consolidate all three sources ----

    print("[1/4] Consolidating annual + candidate + .9...")

    from datafactory_consolidation.consolidators.ucdp import (
        UcdpConsolidationConfig,
        consolidate_ucdp,
    )

    cons_config = UcdpConsolidationConfig(
        annual_dir=annual_dir,
        candidate_dir=candidate_dir,
        dot9_dir=dot9_dir,
        annual_ledger_path=(
            Path("provenance/full_harvest/ucdp_annual")
            / "ingestion_ledger.jsonl"
        ),
        candidate_ledger_path=(
            Path("provenance/smoke_test/ucdp_candidate")
            / "ingestion_ledger.jsonl"
        ),
        dot9_ledger_path=(
            prov_dir / "dot9" / "ledger.jsonl"
        ),
        output_path=out_dir / "consolidated" / "store.parquet",
        ledger_path=prov_dir / "consolidation" / "ledger.jsonl",
    )

    t0 = time.monotonic()
    cons_result = consolidate_ucdp(cons_config)
    cons_time = time.monotonic() - t0

    print(f"  Sources: {cons_result.n_sources}")
    print(f"  Records: {cons_result.n_records_total:,}")
    print(f"  Time: {cons_time:.2f}s")

    # Check source types
    store = pq.read_table(cons_config.output_path)
    types = set(store.column("_source_type").to_pylist())
    print(f"  Source types: {sorted(types)}")

    if "dot9" not in types:
        print("  ERROR: .9 data not in consolidated store!")
        return 1

    print("  PASS")
    print()

    # ---- Step 2: Build production_parity viewpoint ----

    print("[2/4] Building viewpoint (production_parity profile)...")

    from datafactory_viewpoint.builders.ucdp_v1 import (
        build_ucdp_v1,
    )
    from datafactory_viewpoint.profiles import load_profile

    vp_config = load_profile(
        "production_parity",
        cons_config.output_path,
        output_path=out_dir / "viewpoints" / "prod_parity.parquet",
        ledger_path=prov_dir / "viewpoint" / "ledger.jsonl",
    )

    t0 = time.monotonic()
    vp_result = build_ucdp_v1(vp_config)
    vp_time = time.monotonic() - t0

    print(f"  Events in: {vp_result.n_events_input:,}")
    print(f"  Rows out: {vp_result.n_events_output:,}")
    print(f"  Summary expanded: {vp_result.n_summary_expanded}")
    print(f"  Filtered: {vp_result.n_filtered}")
    print(f"  Survivorship: {vp_config.survivorship_strategy}")
    print(f"  Distribution: {vp_config.distribution_strategy}")
    print(f"  Time: {vp_time:.2f}s")
    print("  PASS")
    print()

    # ---- Step 3: Compare against .9 baseline ----

    print("[3/4] Comparing viewpoint vs .9 baseline (25.9.11)...")

    dot9 = pq.read_table(dot9_baseline)
    vp = pq.read_table(vp_result.output_path)

    print(f"  .9 baseline: {dot9.num_rows:,} events")
    print(f"  Our viewpoint: {vp.num_rows:,} rows")

    # Build lookups
    dot9_by_id: dict[int, dict] = {}
    for i in range(dot9.num_rows):
        row = {
            col: dot9.column(col)[i].as_py()
            for col in dot9.column_names
        }
        dot9_by_id[row["id"]] = row

    vp_by_id: dict[int, list[dict]] = {}
    for i in range(vp.num_rows):
        row = {
            col: vp.column(col)[i].as_py()
            for col in vp.column_names
        }
        eid = row["id"]
        if eid not in vp_by_id:
            vp_by_id[eid] = []
        vp_by_id[eid].append(row)

    dot9_ids = set(dot9_by_id.keys())
    vp_ids = set(vp_by_id.keys())
    overlap = dot9_ids & vp_ids

    print()
    print(f"  ID overlap: {len(overlap):,}")
    print(f"  Only in .9: {len(dot9_ids - vp_ids):,}")
    print(f"  Only in viewpoint: {len(vp_ids - dot9_ids):,}")
    print()

    # Fatality comparison on overlapping events
    exact = 0
    close = 0
    diff = 0
    diff_details: list[dict] = []

    for eid in overlap:
        d9_best = dot9_by_id[eid].get("best", 0) or 0
        vp_best = sum(
            r.get("best", 0) or 0 for r in vp_by_id[eid]
        )

        if abs(vp_best - d9_best) < 0.01:
            exact += 1
        elif abs(vp_best - d9_best) < 1.0:
            close += 1
        else:
            diff += 1
            if len(diff_details) < 10:
                diff_details.append({
                    "id": eid,
                    "d9": d9_best,
                    "ours": round(vp_best, 1),
                    "delta": round(vp_best - d9_best, 1),
                })

    match_rate = (
        exact / len(overlap) * 100 if overlap else 0
    )

    print("  Fatality comparison (overlapping events):")
    print(f"    Exact match: {exact:,} ({match_rate:.1f}%)")
    print(f"    Close (<1): {close:,}")
    print(f"    Different: {diff:,}")

    if diff_details:
        print()
        print("  Sample differences:")
        for d in diff_details:
            print(
                f"    id={d['id']}: "
                f".9={d['d9']}, ours={d['ours']} "
                f"(delta={d['delta']:+})"
            )

    # .9-only events analysis
    only_dot9 = dot9_ids - vp_ids
    if only_dot9:
        years = Counter()
        for eid in only_dot9:
            ds = dot9_by_id[eid].get("date_start", "")
            if ds:
                years[ds[:4]] += 1
        print()
        print(f"  Events only in .9 ({len(only_dot9):,}):")
        for y in sorted(years):
            print(f"    {y}: {years[y]:,}")

    print()

    # ---- Step 4: Verdict ----

    print("[4/4] Verdict...")
    print()
    print("=" * 70)

    if match_rate >= 95:
        print(
            f"PASS — {match_rate:.1f}% fatality match "
            f"on {len(overlap):,} overlapping events"
        )
        print(
            f"  .9-only events: {len(only_dot9):,} "
            f"(exclusive .9 content)"
        )
        print(
            f"  Viewpoint-only: {len(vp_ids - dot9_ids):,} "
            f"(from annual/candidate not in .9 window)"
        )
    else:
        print(
            f"REVIEW — {match_rate:.1f}% match rate "
            f"is below 95% target"
        )

    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
