#!/usr/bin/env python3
"""Smoke test: prove the pipeline works with real UCDP data.

Usage:
    UCDP_API_TOKEN=your_token uv run python scripts/smoke_test.py

Fetches 1 year of UCDP/GED Annual data, compiles onto the PRIO-GRID,
and verifies the output makes sense. Requires network access and API token.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np


def main() -> int:
    """Run the smoke test. Returns 0 on PASS, 1 on FAIL."""
    print("=" * 60)
    print("SMOKE TEST: views-datafactory pipeline")
    print("=" * 60)
    print()

    failures: list[str] = []
    data_dir = Path("data/smoke_test")
    provenance_dir = Path("provenance/smoke_test")

    # --- Step 1: Fetch ---
    print("[1/6] Fetching UCDP/GED Annual 2023...")
    from datafactory_harvester.sources.ucdp_annual import (
        UcdpAnnualConfig,
        fetch_ucdp_annual,
    )

    config = UcdpAnnualConfig(
        start_year=2023,
        end_year=2023,
        data_dir=data_dir / "ucdp_annual",
        ledger_path=provenance_dir / "ucdp_annual" / "ingestion_ledger.jsonl",
    )

    try:
        snap_path = fetch_ucdp_annual(config, force_refresh=True)
        print(f"  Snapshot: {snap_path}")
    except Exception as e:
        failures.append(f"Fetch failed: {e}")
        print(f"  FAIL: {e}")
        _report(failures)
        return 1

    # --- Step 2: Inspect ---
    print()
    print("[2/6] Inspecting fetched data...")
    import pyarrow.parquet as pq

    table = pq.read_table(snap_path)
    n_events = table.num_rows
    columns = sorted(table.column_names)
    print(f"  Events: {n_events}")
    print(f"  Columns ({len(columns)}): {columns[:10]}... (+{len(columns)-10} more)")

    # Check critical columns
    for col in ("latitude", "longitude", "date_start", "best", "id"):
        if col in table.column_names:
            print(f"  {col}: PRESENT")
        else:
            failures.append(f"Missing column: {col}")
            print(f"  {col}: MISSING")

    if n_events == 0:
        failures.append("Zero events fetched")

    # --- Step 3: Compile (tiny grid) ---
    print()
    print("[3/6] Compiling onto tiny grid (8 cells)...")
    from datafactory_compilation import CompilationConfig, compile_grid
    from datafactory_priogrid.grid_config import GridConfig
    from datafactory_priogrid.temporal_config import TemporalConfig

    tiny_config = CompilationConfig(
        source_path=snap_path,
        grid_config=GridConfig(resolution=90.0),
        temporal_config=TemporalConfig(start_year=2023, end_year=2023),
        features=(("event_count", "count"), ("fatalities", "sum_best")),
        output_dir=data_dir / "compiled_tiny",
        ledger_path=provenance_dir / "compiler" / "compilation_ledger.jsonl",
    )

    t0 = time.monotonic()
    try:
        tiny_result = compile_grid(tiny_config)
        tiny_time = time.monotonic() - t0
        tiny_grid = np.load(tiny_result / "grid.npy")
        print(f"  Shape: {tiny_grid.shape}")
        print(f"  Time: {tiny_time:.2f}s")
        print(f"  Non-zero cells: {(tiny_grid[:, :, 0] > 0).sum()}")
        print(f"  Total events placed: {tiny_grid[:, :, 0].sum():.0f}")
    except Exception as e:
        failures.append(f"Tiny compile failed: {e}")
        print(f"  FAIL: {e}")

    # --- Step 4: Compile (real grid) ---
    print()
    print("[4/6] Compiling onto REAL grid (259,200 cells × 12 months)...")
    real_config = CompilationConfig(
        source_path=snap_path,
        grid_config=GridConfig(),  # Default: 259,200 cells
        temporal_config=TemporalConfig(start_year=2023, end_year=2023),
        features=(("event_count", "count"), ("fatalities", "sum_best")),
        output_dir=data_dir / "compiled_real",
        ledger_path=provenance_dir / "compiler" / "compilation_ledger.jsonl",
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

        if real_grid.shape != (259_200, 12, 2):
            failures.append(
                f"Wrong shape: {real_grid.shape}, expected (259200, 12, 2)"
            )
        if nonzero_cells == 0:
            failures.append("All cells are zero — no events placed")
        if total_placed < 100:
            failures.append(
                f"Suspiciously few events placed: {total_placed}"
            )

        # Top 5 cells by total event count
        cell_totals = event_counts.sum(axis=1)  # sum across months
        top_indices = np.argsort(cell_totals)[-5:][::-1]
        print("  Top 5 cells by event count:")
        from datafactory_priogrid.cell_generator import pgid_to_latlon

        for idx in top_indices:
            pgid = idx + 1
            lat, lon = pgid_to_latlon(pgid)
            print(
                f"    pgid={pgid} ({float(lat):.1f}, {float(lon):.1f}): "
                f"{cell_totals[idx]:.0f} events"
            )

    except Exception as e:
        failures.append(f"Real compile failed: {e}")
        print(f"  FAIL: {e}")

    # --- Step 5: Provenance ---
    print()
    print("[5/6] Checking provenance...")
    harvest_ledger = (
        provenance_dir / "ucdp_annual" / "ingestion_ledger.jsonl"
    )
    compile_ledger = provenance_dir / "compiler" / "compilation_ledger.jsonl"

    for name, path in [
        ("Harvest ledger", harvest_ledger),
        ("Compile ledger", compile_ledger),
    ]:
        if path.exists():
            last_entry = json.loads(
                path.read_text().strip().splitlines()[-1]
            )
            digest = last_entry.get(
                "content_digest", last_entry.get("output_digest", "?")
            )
            print(f"  {name}: EXISTS (digest: {digest})")
        else:
            failures.append(f"{name} missing: {path}")
            print(f"  {name}: MISSING")

    # --- Step 6: Provenance JSON ---
    prov_path = data_dir / "compiled_real" / "provenance.json"
    if prov_path.exists():
        prov = json.loads(prov_path.read_text())
        print(f"  Provenance JSON: source_digest={prov.get('source_digest')}")
        print(f"  Provenance JSON: output_digest={prov.get('output_digest')}")
    else:
        failures.append("Provenance JSON missing")

    # --- Report ---
    print()
    _report(failures)
    return 1 if failures else 0


def _report(failures: list[str]) -> None:
    """Print final verdict."""
    print("=" * 60)
    if failures:
        print(f"FAIL — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
    else:
        print("PASS — pipeline works with real UCDP data")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
