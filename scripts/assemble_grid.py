#!/usr/bin/env python3
"""Assemble a canonical [T, H, W, F] grid from all data sources.

Usage:
    uv run python scripts/assemble_grid.py
    uv run python scripts/assemble_grid.py --ucdp-grid data/compiled
    uv run python scripts/assemble_grid.py --admin-dir data/gaul_admin

Combines the compiled UCDP conflict grid with PRIO-GRID static
features and GAUL admin boundary codes into a single array. Static
and admin features are broadcast across all time steps.

Output: grid.npy [T, H, W, F] with F = UCDP + static + admin channels.

Admin channels (gaul0_code, gaul1_code, gaul2_code) are categorical
integers stored as float32. Downstream models should treat them as
categorical (embedding / one-hot), not continuous.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    """Assemble the canonical grid."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Assemble canonical grid from all sources"
    )
    parser.add_argument(
        "--ucdp-grid",
        type=Path,
        default=Path("data/compiled"),
        help="Compiled UCDP grid directory",
    )
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=Path("data/raw/priogrid_static"),
        help="PRIO-GRID static Parquet directory",
    )
    parser.add_argument(
        "--admin-dir",
        type=Path,
        default=Path("data/raw/gaul_admin"),
        help="GAUL admin boundary Parquet directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/assembled"),
        help="Output directory",
    )
    args = parser.parse_args()

    # Validate inputs
    grid_path = args.ucdp_grid / "grid.npy"
    pgids_path = args.ucdp_grid / "pgids.npy"
    time_path = args.ucdp_grid / "time_steps.npy"
    features_path = args.ucdp_grid / "feature_names.json"

    for p in [grid_path, pgids_path, time_path, features_path]:
        if not p.exists():
            print(f"FAIL: {p} not found")
            return 1

    if not args.static_dir.exists():
        print(f"FAIL: {args.static_dir} not found")
        return 1

    has_admin = args.admin_dir.exists()
    if not has_admin:
        print(
            f"NOTE: {args.admin_dir} not found, "
            "skipping admin channels"
        )

    print("=" * 60)
    print("GRID ASSEMBLY — All Data Sources")
    print(f"UCDP grid:  {args.ucdp_grid}")
    print(f"Static dir: {args.static_dir}")
    print(f"Admin dir:  {args.admin_dir}"
          f"{'' if has_admin else ' (skipped)'}")
    print(f"Output:     {args.output_dir}")
    print("=" * 60)
    print()

    import numpy as np
    import pyarrow.parquet as pq

    t0 = time.monotonic()

    # Load UCDP grid (mmap to reduce peak memory)
    ucdp_grid = np.load(grid_path, mmap_mode="r")
    pgids = np.load(pgids_path)
    time_steps = np.load(time_path)
    ucdp_features = json.loads(features_path.read_text())

    n_t, n_h, n_w, n_ucdp = ucdp_grid.shape
    print(
        f"UCDP grid: [T={n_t}, H={n_h}, W={n_w}, "
        f"C={n_ucdp}]"
    )
    print(f"UCDP features: {ucdp_features}")

    # Build gid → (row, col) lookup from pgids array
    gid_to_rowcol: dict[int, tuple[int, int]] = {}
    for r in range(n_h):
        for c in range(n_w):
            gid_to_rowcol[int(pgids[r, c])] = (r, c)

    # Discover and sort static variable files
    static_files = sorted(args.static_dir.glob("*.parquet"))
    print(f"Static variables: {len(static_files)}")
    print()

    # Build static [H, W] arrays first (small: 360x720 each)
    static_names = []
    static_spatial: list[np.ndarray] = []

    for sf in static_files:
        var_name = sf.stem
        table = pq.read_table(sf)
        gids = table.column("gid").to_pylist()
        values = table.column("value").to_pylist()

        spatial = np.zeros(
            (n_h, n_w), dtype=np.float32
        )
        n_placed = 0
        for gid, val in zip(gids, values, strict=True):
            if gid in gid_to_rowcol:
                r, c = gid_to_rowcol[gid]
                spatial[r, c] = float(val)
                n_placed += 1

        static_spatial.append(spatial)
        static_names.append(var_name)
        print(
            f"  {var_name}: {n_placed:,} cells placed"
        )

    # ── Admin boundary channels (GAUL codes) ──
    # Only numeric variables become grid channels.
    # String variables (names) are stored separately.
    admin_numeric = (
        "gaul0_code", "gaul1_code", "gaul2_code",
    )

    admin_names: list[str] = []
    admin_spatial: list[np.ndarray] = []

    if has_admin:
        admin_files = sorted(args.admin_dir.glob("*.parquet"))
        print(f"Admin variables: {len(admin_files)}")

        for af in admin_files:
            var_name = af.stem
            if var_name not in admin_numeric:
                continue

            table = pq.read_table(af)
            gids = table.column("gid").to_pylist()
            values = table.column("value").to_pylist()

            spatial = np.full(
                (n_h, n_w), -1.0, dtype=np.float32
            )
            n_placed = 0
            for gid, val in zip(gids, values, strict=True):
                if gid in gid_to_rowcol:
                    r, c = gid_to_rowcol[gid]
                    spatial[r, c] = float(val)
                    n_placed += 1

            admin_spatial.append(spatial)
            admin_names.append(var_name)
            n_unmatched = len(gids) - n_placed
            print(
                f"  {var_name}: {n_placed:,} cells placed"
                f" ({n_unmatched:,} unmatched)"
            )

        print()

    n_static = len(static_names)
    n_admin = len(admin_names)
    n_total = n_ucdp + n_static + n_admin
    all_features = ucdp_features + static_names + admin_names

    print(
        f"Assembling [T={n_t}, H={n_h}, "
        f"W={n_w}, F={n_total}]..."
    )
    print(
        f"  Size: "
        f"{n_t * n_h * n_w * n_total * 4 / 1e9:.1f} GB"
    )

    # Allocate output as memory-mapped file to avoid OOM on
    # servers with limited RAM. Writes go directly to disk;
    # peak memory is ~150 MB instead of 4.6 GB.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "grid.npy"
    assembled = np.lib.format.open_memmap(
        str(output_path),
        mode="w+",
        dtype=np.float32,
        shape=(n_t, n_h, n_w, n_total),
    )

    # Copy UCDP channels
    assembled[:, :, :, :n_ucdp] = ucdp_grid
    del ucdp_grid  # free memory

    # Fill static channels (broadcast in-place)
    for i, spatial in enumerate(static_spatial):
        # spatial is [H, W] — assign to every time step
        assembled[:, :, :, n_ucdp + i] = spatial

    del static_spatial  # free memory

    # Fill admin channels (broadcast in-place)
    for i, spatial in enumerate(admin_spatial):
        assembled[:, :, :, n_ucdp + n_static + i] = spatial

    del admin_spatial  # free memory

    print(f"Assembled shape: {assembled.shape}")
    print(f"  [T={assembled.shape[0]}, "
          f"H={assembled.shape[1]}, "
          f"W={assembled.shape[2]}, "
          f"F={assembled.shape[3]}]")
    print(f"Features ({len(all_features)}):")
    for i, name in enumerate(all_features):
        print(f"  {i:2d}: {name}")

    # Flush mmap to disk (file already exists from open_memmap)
    assembled.flush()
    np.save(args.output_dir / "pgids.npy", pgids)
    np.save(args.output_dir / "time_steps.npy", time_steps)
    (args.output_dir / "feature_names.json").write_text(
        json.dumps(all_features)
    )

    # Provenance
    from datafactory_provenance import compute_file_digest

    output_digest = compute_file_digest(
        args.output_dir / "grid.npy"
    )
    ucdp_digest = compute_file_digest(grid_path)

    provenance = {
        "sources": {
            "ucdp_grid": str(grid_path),
            "ucdp_digest": ucdp_digest,
            "static_dir": str(args.static_dir),
            "static_variables": static_names,
            "admin_dir": str(args.admin_dir),
            "admin_variables": admin_names,
        },
        "output_shape": [n_t, n_h, n_w, n_total],
        "n_features": len(all_features),
        "feature_names": all_features,
        "output_digest": output_digest,
    }
    (args.output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2)
    )

    elapsed = time.monotonic() - t0
    size_gb = (args.output_dir / "grid.npy").stat().st_size / 1e9
    print()
    print(f"Output: {args.output_dir / 'grid.npy'}")
    print(f"Size: {size_gb:.1f} GB")
    print(f"Digest: {output_digest}")
    print(f"Time: {elapsed:.1f}s")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
