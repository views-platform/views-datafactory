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
import sys
import time
from pathlib import Path


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

    import numpy as np
    import xarray as xr

    t0 = time.monotonic()

    # Load grid and metadata
    grid = np.load(grid_path, mmap_mode="r")
    pgids = np.load(pgids_path)
    time_steps = np.load(time_path)
    feature_names = json.loads(features_path.read_text())

    n_t, n_h, n_w, n_f = grid.shape
    print(f"Grid: [T={n_t}, H={n_h}, W={n_w}, F={n_f}]")
    print(f"Features ({n_f}): {feature_names}")
    print()

    # Compute lat/lon cell centers from PRIO-GRID convention
    # Row 0 = south (-89.75°), Row 359 = north (89.75°)
    # Col 0 = west (-179.75°), Col 719 = east (179.75°)
    resolution = 0.5
    lat_centers = np.linspace(
        -90 + resolution / 2,
        90 - resolution / 2,
        n_h,
    )
    lon_centers = np.linspace(
        -180 + resolution / 2,
        180 - resolution / 2,
        n_w,
    )

    # Build xarray Dataset — one variable per feature
    data_vars = {}
    source_sums: dict[str, float] = {}
    for i, name in enumerate(feature_names):
        feature_data = np.asarray(grid[:, :, :, i])
        source_sums[name] = float(feature_data.sum())
        data_vars[name] = (
            ["time", "lat", "lon"],
            feature_data,
        )
        print(f"  {i:2d}: {name}")

    coords = {
        "time": time_steps,
        "lat": lat_centers,
        "lon": lon_centers,
        "pgid": (["lat", "lon"], pgids),
    }

    # Provenance metadata
    attrs = {
        "title": (
            "VIEWS Conflict Data Factory "
            "— Assembled Grid"
        ),
        "crs": "EPSG:4326",
        "resolution_degrees": resolution,
        "source": "views-datafactory",
        "n_features": n_f,
        "feature_order": feature_names,
    }
    if provenance_path.exists():
        prov = json.loads(provenance_path.read_text())
        if "output_digest" in prov:
            attrs["source_digest"] = prov["output_digest"]

    # Freshness indicator (D-03): consumers can check when data
    # was last exported. ISO 8601 UTC timestamp.
    from datetime import datetime, timezone

    attrs["export_timestamp"] = (
        datetime.now(tz=timezone.utc).isoformat()
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

    # Remove existing store if present
    if output.exists():
        import shutil

        shutil.rmtree(output)

    ds.to_zarr(
        output,
        mode="w",
        encoding=encoding,
    )

    # Ensure consolidated metadata for HTTP serving
    import zarr

    zarr.consolidate_metadata(str(output))

    # Round-trip integrity check: read back the zarr store and verify
    # feature sums match the input grid. Catches silent data loss during
    # export (e.g., partial writes, chunking bugs, stale stores).
    # Uses zarr directly and sums one feature at a time to stay within
    # the 8 GB RAM budget on the production server.
    print()
    print("Round-trip integrity check...")
    store = zarr.open(str(output), mode="r")
    n_checked = 0
    for name in feature_names:
        zarr_sum = float(np.array(store[name]).sum())
        src_sum = source_sums[name]
        if abs(src_sum - zarr_sum) > 0.5:
            print(
                f"FAIL: {name} sum mismatch — "
                f"grid={src_sum:.1f}, zarr={zarr_sum:.1f}"
            )
            return 1
        n_checked += 1
    del store
    print(f"  {n_checked} features verified (sums match)")

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
