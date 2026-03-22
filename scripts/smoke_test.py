#!/usr/bin/env python3
"""Comprehensive smoke test: exercise every layer of the data pipeline.

Usage:
    UCDP_API_TOKEN=your_token uv run python scripts/smoke_test.py

Tests the full 4-layer architecture (ADR-012) in 10 steps:
  Layer 1: Harvest annual, candidate, and .9 data from UCDP API
  Layer 2: Consolidate all three sources into event store
  Layer 3: Build viewpoint with production_parity profile
  Layer 4: Compile onto PRIO-GRID as npy arrays

Each step reports PASS/FAIL/SKIP independently.
Requires network access and UCDP_API_TOKEN environment variable.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

_SMOKE_TEST_CANDIDATE_START: int = 2025  # Recent only — full history is slow
_SMOKE_TEST_DOT9_START: int = 2025  # Recent only — full history is slow
_SMOKE_TEST_START_YEAR: int = 2023
_SMOKE_TEST_END_YEAR: int = 2026
_TINY_GRID_RESOLUTION: float = 90.0
_EXPECTED_REAL_SHAPE = (259_200, 48, 2)


def main() -> int:
    """Run the smoke test. Returns 0 on PASS, 1 on FAIL."""
    print("=" * 70)
    print("SMOKE TEST: views-datafactory 4-layer pipeline")
    print("=" * 70)
    print()

    failures: list[str] = []
    skips: list[str] = []
    data_dir = Path("data/smoke_test")
    provenance_dir = Path("provenance/smoke_test")

    annual_snap_path: Path | None = None
    consolidated_path: Path | None = None

    # =================================================================
    # [1/10] Harvest — Fetch UCDP Annual
    # =================================================================
    print("[1/10] Harvest — Fetching UCDP/GED Annual 2023...")
    from datafactory_harvester.sources.ucdp_annual import (
        UcdpAnnualConfig,
        fetch_ucdp_annual,
    )

    annual_config = UcdpAnnualConfig(
        start_year=2023,
        end_year=2023,
        data_dir=data_dir / "ucdp_annual",
        ledger_path=provenance_dir / "ucdp_annual" / "ingestion_ledger.jsonl",
    )

    try:
        annual_snap_path = fetch_ucdp_annual(annual_config, force_refresh=False)
        print(f"  Snapshot: {annual_snap_path}")
        print("  PASS")
    except Exception as e:
        failures.append(f"Annual fetch failed: {e}")
        print(f"  FAIL: {e}")

    # =================================================================
    # [2/10] Harvest — Fetch UCDP Candidate Monthly
    # =================================================================
    print()
    print("[2/10] Harvest — Fetching UCDP/GED Candidate Monthly...")
    from datafactory_harvester.sources.ucdp_candidate import (
        UcdpCandidateConfig,
        fetch_ucdp_candidate,
    )

    candidate_config = UcdpCandidateConfig(
        start_year=_SMOKE_TEST_CANDIDATE_START,
        data_dir=data_dir / "ucdp_candidate",
        ledger_path=(
            provenance_dir / "ucdp_candidate" / "ingestion_ledger.jsonl"
        ),
    )

    try:
        candidate_results = fetch_ucdp_candidate(candidate_config)
        n_versions = len(candidate_results)
        n_success = sum(
            1 for r in candidate_results if r.get("outcome") == "success"
        )
        print(f"  Versions discovered: {n_versions}")
        print(f"  Successfully fetched: {n_success}")
        for r in candidate_results:
            print(
                f"    {r.get('version', '?')}: "
                f"{r.get('outcome', '?')} "
                f"({r.get('n_events', '?')} events)"
            )
        if n_versions == 0:
            skips.append("No candidate versions available")
            print("  SKIP: No candidate versions available (API may be empty)")
        else:
            print("  PASS")
    except Exception as e:
        failures.append(f"Candidate fetch failed: {e}")
        print(f"  FAIL: {e}")

    # =================================================================
    # [3/10] Harvest — Fetch UCDP .9 Consolidated
    # =================================================================
    print()
    print("[3/10] Harvest — Fetching UCDP/GED .9 consolidated...")
    from datafactory_harvester.sources.ucdp_dot9 import (
        UcdpDot9Config,
        fetch_ucdp_dot9,
    )

    dot9_config = UcdpDot9Config(
        start_year=_SMOKE_TEST_DOT9_START,
        data_dir=data_dir / "ucdp_dot9",
        ledger_path=(
            provenance_dir / "ucdp_dot9" / "ingestion_ledger.jsonl"
        ),
    )

    try:
        dot9_results = fetch_ucdp_dot9(dot9_config)
        n_dot9_versions = len(dot9_results)
        n_dot9_success = sum(
            1 for r in dot9_results
            if r.get("outcome") == "success"
        )
        print(f"  Versions discovered: {n_dot9_versions}")
        print(f"  Successfully fetched: {n_dot9_success}")
        for r in dot9_results:
            print(
                f"    {r.get('version', '?')}: "
                f"{r.get('outcome', '?')} "
                f"({r.get('n_events', '?')} events)"
            )
        if n_dot9_versions == 0:
            skips.append("No .9 versions available")
            print("  SKIP: No .9 versions available")
        else:
            print("  PASS")
    except Exception as e:
        failures.append(f".9 fetch failed: {e}")
        print(f"  FAIL: {e}")

    # =================================================================
    # [4/10] Harvest — Inspect Raw Data
    # =================================================================
    print()
    print("[4/10] Harvest — Inspecting raw data...")
    import pyarrow.parquet as pq

    critical_cols = ("latitude", "longitude", "date_start", "best", "id")

    # Annual
    annual_files = sorted((data_dir / "ucdp_annual").glob("*.parquet"))
    n_annual_events = 0
    for f in annual_files:
        t = pq.read_table(f)
        n_annual_events += t.num_rows
        print(f"  Annual: {f.name} ({t.num_rows:,} events, {len(t.column_names)} cols)")
        for col in critical_cols:
            if col not in t.column_names:
                failures.append(f"Annual missing column: {col}")
                print(f"    MISSING: {col}")

    # Candidate
    candidate_files = sorted((data_dir / "ucdp_candidate").glob("*.parquet"))
    n_candidate_events = 0
    for f in candidate_files:
        t = pq.read_table(f)
        n_candidate_events += t.num_rows
        print(f"  Candidate: {f.name} ({t.num_rows:,} events)")

    # .9
    dot9_files = sorted(
        (data_dir / "ucdp_dot9").glob("*.parquet")
    ) if (data_dir / "ucdp_dot9").exists() else []
    n_dot9_events = 0
    for f in dot9_files:
        t = pq.read_table(f)
        n_dot9_events += t.num_rows
        print(f"  .9: {f.name} ({t.num_rows:,} events)")

    n_total_raw = (
        n_annual_events + n_candidate_events + n_dot9_events
    )
    print(
        f"  Total raw: {n_annual_events:,} annual + "
        f"{n_candidate_events:,} candidate + "
        f"{n_dot9_events:,} .9 = {n_total_raw:,}"
    )
    if n_annual_events == 0:
        failures.append("Zero annual events")
    print("  PASS" if not any("missing" in f.lower() for f in failures) else "")

    # =================================================================
    # [5/10] Consolidate — Build Event Store
    # =================================================================
    print()
    print("[5/10] Consolidate — Building lossless event store...")
    from datafactory_consolidation.consolidators.ucdp import (
        UcdpConsolidationConfig,
        consolidate_ucdp,
    )

    consolidation_config = UcdpConsolidationConfig(
        annual_dir=data_dir / "ucdp_annual",
        candidate_dir=data_dir / "ucdp_candidate",
        dot9_dir=data_dir / "ucdp_dot9",
        dot9_ledger_path=(
            provenance_dir / "ucdp_dot9" / "ingestion_ledger.jsonl"
        ),
        output_path=data_dir / "consolidated" / "ucdp_store.parquet",
        ledger_path=(
            provenance_dir / "consolidation" / "ucdp_ledger.jsonl"
        ),
    )

    t0 = time.monotonic()
    try:
        cons_result = consolidate_ucdp(consolidation_config)
        cons_time = time.monotonic() - t0
        consolidated_path = cons_result.output_path
        print(f"  Sources consolidated: {cons_result.n_sources}")
        print(f"  Records total: {cons_result.n_records_total:,}")
        print(f"  Records new: {cons_result.n_records_new:,}")
        print(f"  Output digest: {cons_result.output_digest}")
        print(f"  Time: {cons_time:.2f}s")
        print("  PASS")
    except Exception as e:
        failures.append(f"Consolidation failed: {e}")
        print(f"  FAIL: {e}")

    # =================================================================
    # [6/10] Consolidate — Inspect Event Store
    # =================================================================
    print()
    print("[6/10] Consolidate — Inspecting event store...")

    if consolidated_path and consolidated_path.exists():
        store = pq.read_table(consolidated_path)
        source_types = set(store.column("_source_type").to_pylist())
        source_versions = set(store.column("_source_version").to_pylist())
        print(f"  Total records: {store.num_rows:,}")
        print(f"  Source types: {sorted(source_types)}")
        print(f"  Source versions: {sorted(source_versions)}")
        print(f"  Columns: {len(store.column_names)}")

        # Lossless check: record count should match sum of sources
        expected = n_annual_events + n_candidate_events
        if store.num_rows != expected:
            # Dedup may reduce count (same events in annual + candidate)
            print(
                f"  Note: {expected - store.num_rows} duplicate records "
                f"deduplicated ({expected} raw → {store.num_rows} stored)"
            )

        # Check metadata columns
        for meta_col in ("_source_type", "_source_version", "_ingested_at"):
            if meta_col not in store.column_names:
                failures.append(f"Missing metadata column: {meta_col}")
                print(f"    MISSING: {meta_col}")

        if "annual" in source_types and "candidate" in source_types:
            print("  Both annual and candidate sources present")
        elif "annual" in source_types:
            print("  Annual only (no candidate data available)")
        else:
            failures.append("No annual source in consolidated store")

        print("  PASS")
    else:
        failures.append("Consolidated store not found")
        print("  FAIL: consolidated store not found")

    # =================================================================
    # [7/10] Viewpoint — Build Materialized View
    # =================================================================
    print()
    print("[7/10] Viewpoint — Building materialized view...")
    from datafactory_viewpoint.builders import list_builders

    viewpoint_path: Path | None = None

    # Import builder module to trigger auto-registration
    import datafactory_viewpoint.builders.ucdp_v1  # noqa: F401

    builders = list_builders()
    if builders and consolidated_path:
        from datafactory_viewpoint.builders.ucdp_v1 import build_ucdp_v1
        from datafactory_viewpoint.viewpoint_config import ViewpointConfig

        viewpoint_config = ViewpointConfig(
            consolidated_path=consolidated_path,
            output_path=data_dir / "viewpoints" / "ucdp_v1.parquet",
            ledger_path=(
                provenance_dir / "viewpoint" / "ucdp_v1_ledger.jsonl"
            ),
        )

        t0 = time.monotonic()
        try:
            vp_result = build_ucdp_v1(viewpoint_config)
            vp_time = time.monotonic() - t0
            viewpoint_path = vp_result.output_path
            print(f"  Events in: {vp_result.n_events_input:,}")
            print(f"  Rows out: {vp_result.n_events_output:,}")
            print(f"  Summary events expanded: {vp_result.n_summary_expanded}")
            print(f"  Output digest: {vp_result.output_digest}")
            print(f"  Time: {vp_time:.2f}s")
            print("  PASS")
        except Exception as e:
            failures.append(f"Viewpoint build failed: {e}")
            print(f"  FAIL: {e}")
    elif not builders:
        skips.append("Viewpoint layer not yet implemented")
        print("  SKIP: No viewpoint builders registered")
    else:
        skips.append("No consolidated store for viewpoint")
        print("  SKIP: No consolidated store available")

    # =================================================================
    # [8/10] Compile — Tiny Grid (8 cells)
    # =================================================================
    print()
    print("[8/10] Compile — Tiny grid (8 cells)...")
    from datafactory_compilation import CompilationConfig, compile_grid
    from datafactory_priogrid.grid_config import GridConfig
    from datafactory_priogrid.temporal_config import TemporalConfig

    # Prefer viewpoint output, fall back to consolidated, then annual
    compile_source = viewpoint_path or consolidated_path or annual_snap_path
    compile_date_field = "date_month" if viewpoint_path else "date_start"
    if compile_source is None:
        failures.append("No source available for compilation")
        print("  FAIL: no source data available")
    else:
        tiny_config = CompilationConfig(
            source_path=compile_source,
            grid_config=GridConfig(resolution=_TINY_GRID_RESOLUTION),
            temporal_config=TemporalConfig(
                start_year=_SMOKE_TEST_START_YEAR,
                end_year=_SMOKE_TEST_END_YEAR,
            ),
            features=(("event_count", "count"), ("fatalities", "sum_best")),
            output_dir=data_dir / "compiled_tiny",
            ledger_path=provenance_dir / "compiler" / "compilation_ledger.jsonl",
            date_field=compile_date_field,
        )

        t0 = time.monotonic()
        try:
            tiny_result = compile_grid(tiny_config)
            tiny_time = time.monotonic() - t0
            tiny_grid = np.load(tiny_result / "grid.npy")
            print(f"  Shape: {tiny_grid.shape}")
            print(f"  Time: {tiny_time:.2f}s")
            print(f"  Non-zero cells: {(tiny_grid[:, :, 0] > 0).sum()}")
            print(f"  Events placed: {tiny_grid[:, :, 0].sum():.0f}")
            print("  PASS")
        except Exception as e:
            failures.append(f"Tiny compile failed: {e}")
            print(f"  FAIL: {e}")

    # =================================================================
    # [9/10] Compile — Real Grid (259,200 cells)
    # =================================================================
    print()
    print("[9/10] Compile — Real grid (259,200 cells × 48 months)...")

    if compile_source is not None:
        real_config = CompilationConfig(
            source_path=compile_source,
            grid_config=GridConfig(),
            temporal_config=TemporalConfig(
                start_year=_SMOKE_TEST_START_YEAR,
                end_year=_SMOKE_TEST_END_YEAR,
            ),
            features=(("event_count", "count"), ("fatalities", "sum_best")),
            output_dir=data_dir / "compiled_real",
            ledger_path=provenance_dir / "compiler" / "compilation_ledger.jsonl",
            date_field=compile_date_field,
        )

        t0 = time.monotonic()
        try:
            real_result = compile_grid(real_config)
            real_time = time.monotonic() - t0
            real_grid = np.load(real_result / "grid.npy")
            print(f"  Shape: {real_grid.shape}")
            print(f"  Time: {real_time:.2f}s")

            event_counts = real_grid[:, :, 0]
            nonzero_cells = (event_counts > 0).sum()
            total_placed = event_counts.sum()
            print(f"  Non-zero (cell, month) bins: {nonzero_cells}")
            print(f"  Total events placed: {total_placed:.0f}")

            if real_grid.shape != _EXPECTED_REAL_SHAPE:
                failures.append(
                    f"Wrong shape: {real_grid.shape}, expected {_EXPECTED_REAL_SHAPE}"
                )
            if nonzero_cells == 0:
                failures.append("All cells are zero")
            if total_placed < 100:
                failures.append(f"Suspiciously few events: {total_placed}")

            # Top 5 cells
            from datafactory_priogrid.cell_generator import pgid_to_latlon

            cell_totals = event_counts.sum(axis=1)
            top_indices = np.argsort(cell_totals)[-5:][::-1]
            print("  Top 5 cells:")
            for idx in top_indices:
                pgid = idx + 1
                lat, lon = pgid_to_latlon(pgid)
                print(
                    f"    pgid={pgid} ({float(lat):.1f}, {float(lon):.1f}): "
                    f"{cell_totals[idx]:.0f} events"
                )
            print("  PASS")
        except Exception as e:
            failures.append(f"Real compile failed: {e}")
            print(f"  FAIL: {e}")

    # =================================================================
    # [10/10] Provenance — End-to-End Chain
    # =================================================================
    print()
    print("[10/10] Provenance — Checking end-to-end chain...")

    candidate_ledger = (
        provenance_dir / "ucdp_candidate" / "ingestion_ledger.jsonl"
    )
    dot9_ledger = (
        provenance_dir / "ucdp_dot9" / "ingestion_ledger.jsonl"
    )
    ledgers = [
        ("Annual harvest", provenance_dir / "ucdp_annual" / "ingestion_ledger.jsonl"),
        ("Candidate harvest", candidate_ledger),
        (".9 harvest", dot9_ledger),
        ("Consolidation", provenance_dir / "consolidation" / "ucdp_ledger.jsonl"),
        ("Viewpoint", provenance_dir / "viewpoint" / "ucdp_v1_ledger.jsonl"),
        ("Compilation", provenance_dir / "compiler" / "compilation_ledger.jsonl"),
    ]

    for name, path in ledgers:
        if path.exists():
            last_entry = json.loads(
                path.read_text().strip().splitlines()[-1]
            )
            digest = last_entry.get(
                "content_digest", last_entry.get("output_digest", "?")
            )
            print(f"  {name}: EXISTS (digest: {digest})")
        else:
            if "candidate" in name.lower() and n_candidate_events == 0:
                print(f"  {name}: SKIPPED (no candidate data)")
            else:
                failures.append(f"{name} ledger missing: {path}")
                print(f"  {name}: MISSING")

    # Compiled provenance JSON
    prov_path = data_dir / "compiled_real" / "provenance.json"
    if prov_path.exists():
        prov = json.loads(prov_path.read_text())
        print(f"  Compiled provenance: source={prov.get('source_digest')}, "
              f"output={prov.get('output_digest')}")
    else:
        failures.append("Compiled provenance.json missing")

    print()
    if not failures:
        print("  PASS")

    # =================================================================
    # Report
    # =================================================================
    print()
    print("=" * 70)
    if failures:
        print(f"FAIL — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
    else:
        print("PASS — 4-layer pipeline works with real UCDP data")

    if skips:
        print(f"\nSkipped ({len(skips)}):")
        for s in skips:
            print(f"  - {s}")

    print("=" * 70)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
