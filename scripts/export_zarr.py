#!/usr/bin/env python3
"""Export assembled grid to zarr store for HTTP serving.

Usage:
    uv run python scripts/export_zarr.py
    uv run python scripts/export_zarr.py --input data/assembled
    uv run python scripts/export_zarr.py --output data/zarr
    uv run python scripts/export_zarr.py --chunks-time 12

Reads an assembled grid directory (grid.npy + pgids.npy +
time_steps.npy + feature_names.json) and produces an
xarray-compatible zarr store.

Each feature becomes a separate data variable with dimensions
(time, lat, lon). Coordinates include lat/lon cell centers,
datetime timestamps, and PRIO-GRID cell IDs as a non-dimension
coordinate.

The zarr store can be served by any static HTTP server (nginx,
caddy). Consumers open it with:

    import xarray as xr
    ds = xr.open_zarr("https://yourserver/grid.zarr")
    ethiopia = ds["ged_sb_best"].sel(lat=slice(3, 15), lon=slice(33, 48))
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import zarr


def main() -> int:
    """Export assembled grid to zarr."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Export assembled grid to zarr store"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/assembled"),
        help="Assembled grid directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output zarr store path",
    )
    parser.add_argument(
        "--chunks-time",
        type=int,
        default=12,
        help="Temporal chunk size in months (default: 12)",
    )
    parser.add_argument(
        "--skip-if-unchanged",
        action="store_true",
        help=(
            "Skip export if assembly digest matches the "
            "zarr store's source_digest"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force export, bypassing content-addressed skip",
    )
    args = parser.parse_args()

    grid_path = args.input / "grid.npy"
    pgids_path = args.input / "pgids.npy"
    time_path = args.input / "time_steps.npy"
    features_path = args.input / "feature_names.json"
    provenance_path = args.input / "provenance.json"
    output = args.output or (args.input / "grid.zarr")

    for p in [grid_path, pgids_path, time_path, features_path]:
        if not p.exists():
            print(f"FAIL: {p} not found")
            return 1

    print("=" * 60)
    print("ZARR EXPORT")
    print(f"Input:  {args.input}")
    print(f"Output: {output}")
    print(f"Chunks: {args.chunks_time} months (time)")
    print("=" * 60)
    print()

    # Content-addressed skip (ADR-041): compare assembly digest
    # against zarr store, record outcome in ledger.
    if args.skip_if_unchanged and not args.force:
        from datafactory_provenance import (
            DIGEST_SCHEME,
            LEDGER_VERSION,
            append_ledger_entry,
            check_export_skip,
        )

        verdict = check_export_skip(provenance_path, output)
        if verdict.should_skip:
            print(f"SKIP: {verdict.reason}")
            sentinel = args.input / ".exports_required"
            if sentinel.exists():
                sentinel.unlink()
                print("  Cleared .exports_required sentinel")
            ledger_path = args.input / "export_ledger.jsonl"
            append_ledger_entry(ledger_path, {
                "stage": "export",
                "outcome": "unchanged",
                "ledger_version": LEDGER_VERSION,
                "digest_algorithm": DIGEST_SCHEME,
            })
            print("PASS")
            return 0
        elif not verdict.should_skip and verdict.reason:
            print(f"{verdict.reason} — re-exporting")

    import numpy as np
    import xarray as xr

    t0 = time.monotonic()

    # Load grid and metadata
    grid = np.load(grid_path, mmap_mode="r")
    pgids = np.load(pgids_path)
    time_steps = np.load(time_path)
    feature_names = json.loads(features_path.read_text())

    from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG

    DEFAULT_GRID_CONFIG.assert_grid_shape(grid)
    n_t, n_h, n_w, n_f = grid.shape
    print(f"Grid: [T={n_t}, H={n_h}, W={n_w}, F={n_f}]")
    print(f"Features ({n_f}): {feature_names}")
    print()

    # Compute lat/lon cell centers from PRIO-GRID convention
    res = DEFAULT_GRID_CONFIG.resolution
    lat_centers = np.linspace(
        DEFAULT_GRID_CONFIG.south + res / 2,
        DEFAULT_GRID_CONFIG.north - res / 2,
        n_h,
    )
    lon_centers = np.linspace(
        DEFAULT_GRID_CONFIG.west + res / 2,
        DEFAULT_GRID_CONFIG.east - res / 2,
        n_w,
    )

    # Build xarray Dataset — one variable per feature
    data_vars = {}
    source_sums: dict[str, float] = {}
    for i, name in enumerate(feature_names):
        feature_slice = grid[:, :, :, i]
        source_sums[name] = float(feature_slice.sum())
        data_vars[name] = (
            ["time", "lat", "lon"],
            feature_slice,
        )
        print(f"  {i:2d}: {name}")

    coords = {
        "time": time_steps,
        "lat": lat_centers,
        "lon": lon_centers,
        "pgid": (["lat", "lon"], pgids),
    }

    # Source-digest gate: verify grid.npy matches assembly provenance
    # before exporting. Prevents serving stale data (C-253).
    from datafactory_provenance import compute_file_digest

    print("Computing grid digest (streaming)...")
    grid_digest = compute_file_digest(grid_path)
    print(f"  grid.npy digest: {grid_digest}")

    if provenance_path.exists():
        prov = json.loads(provenance_path.read_text())
        recorded = prov.get("output_digest")
        if recorded and recorded != grid_digest:
            print(
                f"ABORT: grid.npy digest ({grid_digest}) does "
                f"not match provenance.json ({recorded}). "
                f"grid.npy was modified after assembly — "
                f"re-run: uv run python scripts/assemble_grid.py"
            )
            return 1
        if recorded:
            print(f"  provenance.json digest: {recorded} — MATCH")
    else:
        print("  provenance.json not found — skipping gate")

    # Provenance metadata
    attrs = {
        "title": (
            "VIEWS Conflict Data Factory "
            "— Assembled Grid"
        ),
        "crs": "EPSG:4326",
        "resolution_degrees": res,
        "source": "views-datafactory",
        "n_features": n_f,
        "feature_order": feature_names,
        "source_digest": grid_digest,
    }

    # Freshness indicator (D-03): consumers can check when data
    # was last exported. ISO 8601 UTC timestamp.
    attrs["export_timestamp"] = (
        datetime.now(tz=UTC).isoformat()
    )

    # Data boundary: last month with real UCDP observations.
    # The grid is pre-allocated through --end-year (ADR-003) but
    # only months through this boundary have observed data; later
    # months are zero-filled padding.
    ucdp_indices = [
        i for i, name in enumerate(feature_names)
        if name.startswith("ged_")
    ]
    if ucdp_indices:
        ucdp_slice = grid[:, :, :, ucdp_indices]
        has_data = ucdp_slice.sum(axis=(1, 2, 3)) > 0
        valid_steps = np.where(has_data)[0]
        if len(valid_steps) > 0:
            from datafactory_priogrid import to_views_month_id

            last_idx = int(valid_steps[-1])
            last_dt = time_steps[last_idx]
            last_mid = int(to_views_month_id(last_dt))
            attrs["last_valid_month_id"] = last_mid
            attrs["last_valid_date"] = str(last_dt)
            print(
                f"Last valid UCDP month: {last_mid} "
                f"({last_dt})"
            )

    ds = xr.Dataset(
        data_vars=data_vars,
        coords=coords,
        attrs=attrs,
    )

    print()
    print(f"Dataset: {ds.dims}")
    print(
        f"Size: "
        f"{n_t * n_h * n_w * n_f * 4 / 1e9:.1f} GB "
        f"(float32)"
    )

    # Write zarr with chunking
    encoding = {
        name: {"chunks": (args.chunks_time, n_h, n_w)}
        for name in feature_names
    }

    # Atomic swap (C-144): write to .tmp, verify, then rename into
    # the live path. Shrinks the consumer-visible gap to a single rename.
    tmp_output = output.parent / (output.name + ".tmp")

    if tmp_output.exists():
        shutil.rmtree(tmp_output)

    try:
        ds.to_zarr(
            tmp_output,
            mode="w",
            encoding=encoding,
        )
        zarr.consolidate_metadata(str(tmp_output))

        print()
        print("Round-trip integrity check...")
        store = zarr.open(str(tmp_output), mode="r")
        n_checked = 0
        for name in feature_names:
            zarr_sum = float(np.array(store[name]).sum())
            src_sum = source_sums[name]
            if abs(src_sum - zarr_sum) > 0.5:
                print(
                    f"FAIL: {name} sum mismatch — "
                    f"grid={src_sum:.1f}, zarr={zarr_sum:.1f}"
                )
                del store
                shutil.rmtree(tmp_output)
                return 1
            n_checked += 1
        del store
        print(f"  {n_checked} features verified (sums match)")

        old_output = output.parent / (output.name + ".old")
        if old_output.exists():
            shutil.rmtree(old_output)
        if output.exists():
            os.rename(str(output), str(old_output))
        os.rename(str(tmp_output), str(output))
        if old_output.exists():
            shutil.rmtree(old_output)
    except Exception:
        if tmp_output.exists():
            shutil.rmtree(tmp_output)
        raise

    # Clear assembly sentinel — this export matches the current grid
    sentinel = args.input / ".exports_required"
    if sentinel.exists():
        sentinel.unlink()
        print("  Cleared .exports_required sentinel")

    elapsed = time.monotonic() - t0

    # Compute store size
    store_bytes = sum(
        f.stat().st_size
        for f in output.rglob("*")
        if f.is_file()
    )

    print()
    print(f"Output: {output}")
    print(f"Store size: {store_bytes / 1e9:.1f} GB")
    print(f"Chunks: {args.chunks_time} months x "
          f"{n_h} lat x {n_w} lon")
    print(f"Time: {elapsed:.1f}s")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
