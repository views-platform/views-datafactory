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
    for i, name in enumerate(feature_names):
        data_vars[name] = (
            ["time", "lat", "lon"],
            np.asarray(grid[:, :, :, i]),
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
    }
    if provenance_path.exists():
        prov = json.loads(provenance_path.read_text())
        if "output_digest" in prov:
            attrs["source_digest"] = prov["output_digest"]

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
