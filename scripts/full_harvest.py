#!/usr/bin/env python3
"""Full-scale UCDP harvest + consolidation + viewpoint.

Usage:
    UCDP_API_TOKEN=your_token uv run python scripts/full_harvest.py

Fetches the complete UCDP history:
  - Annual v25.1 (1989-2024, ~385K events) — reuses if exists
  - ALL candidate versions (2018-2026, ~98 versions, ~210K events)
  - ALL .9 versions (2018-2026, ~98 versions, ~2.2M events)

Consolidates into a single lossless event store, builds a viewpoint
with the production_parity profile, and reports statistics.

Total runtime: ~13 minutes (mostly API fetching).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def main() -> int:
    """Run the full-scale harvest."""
    print("=" * 70)
    print("FULL-SCALE UCDP HARVEST + CONSOLIDATION")
    print("Jan 1989 – Feb 2026")
    print("=" * 70)
    print()

    data_dir = Path("data/full_harvest")
    prov_dir = Path("provenance/full_harvest")
    t_start = time.monotonic()

    # ---- Step 1: Annual ----
    print("[1/5] Annual v25.1 (1989-2024)...")

    from datafactory_harvester.sources.ucdp_annual import (
        UcdpAnnualConfig,
        fetch_ucdp_annual,
    )

    annual_config = UcdpAnnualConfig(
        data_dir=data_dir / "ucdp_annual",
        ledger_path=(
            prov_dir / "ucdp_annual" / "ingestion_ledger.jsonl"
        ),
    )

    try:
        annual_path = fetch_ucdp_annual(
            annual_config, force_refresh=False
        )
        import pyarrow.parquet as pq

        t = pq.read_table(annual_path)
        print(f"  {t.num_rows:,} events — {annual_path}")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        return 1

    # ---- Step 2: ALL Candidates ----
    print()
    print("[2/5] ALL candidate versions (2018-2026)...")

    from datafactory_harvester.sources.ucdp_candidate import (
        UcdpCandidateConfig,
        fetch_ucdp_candidate,
    )

    candidate_config = UcdpCandidateConfig(
        data_dir=data_dir / "ucdp_candidate",
        ledger_path=(
            prov_dir / "ucdp_candidate"
            / "ingestion_ledger.jsonl"
        ),
    )

    t0 = time.monotonic()
    try:
        cand_results = fetch_ucdp_candidate(candidate_config)
        cand_time = time.monotonic() - t0
        n_cand = len(cand_results)
        n_success = sum(
            1 for r in cand_results
            if r.get("outcome") in ("success", "unchanged")
        )
        print(f"  {n_cand} versions, {n_success} ok")
        print(f"  Time: {cand_time:.1f}s")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        return 1

    # ---- Step 3: ALL .9 Versions ----
    print()
    print("[3/5] ALL .9 versions (2018-2026)...")

    from datafactory_harvester.sources.ucdp_dot9 import (
        UcdpDot9Config,
        fetch_ucdp_dot9,
    )

    dot9_config = UcdpDot9Config(
        data_dir=data_dir / "ucdp_dot9",
        ledger_path=(
            prov_dir / "ucdp_dot9" / "ingestion_ledger.jsonl"
        ),
    )

    t0 = time.monotonic()
    try:
        dot9_results = fetch_ucdp_dot9(dot9_config)
        dot9_time = time.monotonic() - t0
        n_dot9 = len(dot9_results)
        n_dot9_ok = sum(
            1 for r in dot9_results
            if r.get("outcome") in ("success", "unchanged")
        )
        print(f"  {n_dot9} versions, {n_dot9_ok} ok")
        print(f"  Time: {dot9_time:.1f}s")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        return 1

    # ---- Step 4: Consolidate ----
    print()
    print("[4/5] Consolidating all three sources...")

    from datafactory_consolidation.consolidators.ucdp import (
        UcdpConsolidationConfig,
        consolidate_ucdp,
    )

    cons_config = UcdpConsolidationConfig(
        annual_dir=data_dir / "ucdp_annual",
        candidate_dir=data_dir / "ucdp_candidate",
        dot9_dir=data_dir / "ucdp_dot9",
        annual_ledger_path=(
            prov_dir / "ucdp_annual" / "ingestion_ledger.jsonl"
        ),
        candidate_ledger_path=(
            prov_dir / "ucdp_candidate"
            / "ingestion_ledger.jsonl"
        ),
        dot9_ledger_path=(
            prov_dir / "ucdp_dot9" / "ingestion_ledger.jsonl"
        ),
        output_path=(
            data_dir / "consolidated" / "ucdp_store.parquet"
        ),
        ledger_path=(
            prov_dir / "consolidation" / "ledger.jsonl"
        ),
    )

    t0 = time.monotonic()
    try:
        cons_result = consolidate_ucdp(cons_config)
        cons_time = time.monotonic() - t0

        store = pq.read_table(cons_config.output_path)
        types = store.column("_source_type").to_pylist()
        from collections import Counter

        type_counts = Counter(types)

        print(f"  Total records: {cons_result.n_records_total:,}")
        print(f"  Sources: {cons_result.n_sources}")
        print("  Source breakdown:")
        for stype, count in sorted(type_counts.items()):
            print(f"    {stype}: {count:,}")
        print(f"  Time: {cons_time:.1f}s")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        return 1

    # ---- Step 5: Build viewpoint ----
    print()
    print("[5/5] Building production_parity viewpoint...")

    from datafactory_viewpoint.builders.ucdp_v1 import (
        build_ucdp_v1,
    )
    from datafactory_viewpoint.profiles import load_profile

    vp_config = load_profile(
        "production_parity",
        cons_config.output_path,
        output_path=(
            data_dir / "viewpoints" / "production_parity.parquet"
        ),
        ledger_path=(
            prov_dir / "viewpoint" / "ledger.jsonl"
        ),
    )

    t0 = time.monotonic()
    try:
        vp_result = build_ucdp_v1(vp_config)
        vp_time = time.monotonic() - t0

        print(f"  Events in: {vp_result.n_events_input:,}")
        print(f"  Rows out: {vp_result.n_events_output:,}")
        print(f"  Summary expanded: {vp_result.n_summary_expanded}")
        print(f"  Filtered: {vp_result.n_filtered}")
        print(f"  Time: {vp_time:.1f}s")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        return 1

    # ---- Report ----
    total_time = time.monotonic() - t_start

    print()
    print("=" * 70)
    print("COMPLETE — full UCDP history consolidated")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Store: {cons_config.output_path}")
    print(f"  Viewpoint: {vp_config.output_path}")
    print(f"  Records: {cons_result.n_records_total:,}")
    print(f"  Viewpoint rows: {vp_result.n_events_output:,}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
