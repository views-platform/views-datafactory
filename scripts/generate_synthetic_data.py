"""Generate synthetic compiled grids with planted known-answer values.

Creates a minimal directory structure that assembly, zarr export, and
consumer scripts can process. Used for fast end-to-end testing (~seconds
instead of ~hours) and known-answer verification at every layer boundary.

Usage:
    uv run python scripts/generate_synthetic_data.py [--output-dir /tmp/synthetic]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Grid constants ──────────────────────────────────────────
NROW, NCOL = 360, 720

# ── Planted cells (both must be in land_pgids) ─────────────
# Near Nairobi: lat≈-1.2°, lon≈36.8° and lon≈37.2°
ROW_A, COL_A = 177, 433  # pgid = 127874
ROW_B, COL_B = 177, 434  # pgid = 127875
PGID_A = ROW_A * NCOL + COL_A + 1
PGID_B = ROW_B * NCOL + COL_B + 1

# ── Temporal ranges ─────────────────────────────────────────
UCDP_MONTHS = np.arange("2020-01", "2021-01", dtype="datetime64[M]")  # 12
ACLED_MONTHS = np.arange("2020-04", "2020-10", dtype="datetime64[M]")  # 6

UCDP_FEATURES = ["ged_sb_best", "ged_ns_best", "ged_os_best"]
ACLED_FEATURES = ["acled_count", "acled_fatalities"]

# ── Planted values ──────────────────────────────────────────
# Format: (row, col, time_idx, feature_idx, value)
UCDP_PLANTS = [
    (ROW_A, COL_A, 0, 0, 7.0),    # ged_sb_best, Jan 2020
    (ROW_A, COL_A, 0, 1, 3.0),    # ged_ns_best, Jan 2020
    (ROW_A, COL_A, 0, 2, 1.0),    # ged_os_best, Jan 2020
    (ROW_A, COL_A, 6, 0, 11.0),   # ged_sb_best, Jul 2020
    (ROW_A, COL_A, 6, 1, 5.0),    # ged_ns_best, Jul 2020
    (ROW_A, COL_A, 6, 2, 2.0),    # ged_os_best, Jul 2020
    (ROW_B, COL_B, 0, 0, 99.0),   # ged_sb_best, Jan 2020 (cell B)
]

ACLED_PLANTS = [
    (ROW_A, COL_A, 0, 0, 4.0),    # acled_count, Apr 2020 (ACLED month 0)
    (ROW_A, COL_A, 0, 1, 8.0),    # acled_fatalities, Apr 2020
    (ROW_A, COL_A, 3, 0, 6.0),    # acled_count, Jul 2020 (ACLED month 3)
    (ROW_A, COL_A, 3, 1, 12.0),   # acled_fatalities, Jul 2020
]

STATIC_PLANTS = {
    PGID_A: 1250.0,
    PGID_B: 500.0,
}

ADMIN_PLANTS = {
    PGID_A: 133,
    PGID_B: 133,
}


def _make_pgids() -> np.ndarray:
    pgids = np.zeros((NROW, NCOL), dtype=np.int32)
    for row in range(NROW):
        for col in range(NCOL):
            pgids[row, col] = row * NCOL + col + 1
    return pgids


def _make_grid(
    shape: tuple[int, ...],
    plants: list[tuple[int, int, int, int, float]],
) -> np.ndarray:
    grid = np.zeros(shape, dtype=np.float32)
    for row, col, t, f, val in plants:
        grid[t, row, col, f] = val
    return grid


def generate(output_dir: Path) -> dict:
    """Create synthetic compiled grids with planted known-answer values.

    Returns metadata dict with planted values for assertion.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── UCDP compiled grid ──────────────────────────────────
    ucdp_dir = output_dir / "compiled"
    ucdp_dir.mkdir(parents=True, exist_ok=True)

    n_t = len(UCDP_MONTHS)
    n_f = len(UCDP_FEATURES)
    ucdp_grid = _make_grid((n_t, NROW, NCOL, n_f), UCDP_PLANTS)
    np.save(ucdp_dir / "grid.npy", ucdp_grid)

    pgids = _make_pgids()
    np.save(ucdp_dir / "pgids.npy", pgids)
    np.save(ucdp_dir / "time_steps.npy", UCDP_MONTHS)
    (ucdp_dir / "feature_names.json").write_text(json.dumps(UCDP_FEATURES))

    print(f"UCDP: [{n_t}, {NROW}, {NCOL}, {n_f}] = {ucdp_grid.nbytes / 1e6:.0f} MB")

    # ── ACLED compiled grid ─────────────────────────────────
    acled_dir = ucdp_dir / "acled"
    acled_dir.mkdir(parents=True, exist_ok=True)

    n_t_acled = len(ACLED_MONTHS)
    n_f_acled = len(ACLED_FEATURES)
    acled_grid = _make_grid((n_t_acled, NROW, NCOL, n_f_acled), ACLED_PLANTS)
    np.save(acled_dir / "grid.npy", acled_grid)

    np.save(acled_dir / "pgids.npy", pgids)
    np.save(acled_dir / "time_steps.npy", ACLED_MONTHS)
    (acled_dir / "feature_names.json").write_text(json.dumps(ACLED_FEATURES))

    acled_mb = acled_grid.nbytes / 1e6
    print(f"ACLED: [{n_t_acled}, {NROW}, {NCOL}, {n_f_acled}] = {acled_mb:.0f} MB")

    # ── Static variables ────────────────────────────────────
    static_dir = output_dir / "raw" / "priogrid_static"
    static_dir.mkdir(parents=True, exist_ok=True)

    static_df = pd.DataFrame({
        "gid": list(STATIC_PLANTS.keys()),
        "value": list(STATIC_PLANTS.values()),
    })
    static_df.to_parquet(static_dir / "landarea.parquet", index=False)
    print(f"Static: {len(static_df)} cells")

    # ── Admin boundaries ────────────────────────────────────
    admin_dir = output_dir / "raw" / "gaul_admin"
    admin_dir.mkdir(parents=True, exist_ok=True)

    admin_df = pd.DataFrame({
        "gid": list(ADMIN_PLANTS.keys()),
        "value": list(ADMIN_PLANTS.values()),
    })
    admin_df.to_parquet(admin_dir / "gaul0_code.parquet", index=False)
    print(f"Admin: {len(admin_df)} cells")

    total_mb = (ucdp_grid.nbytes + acled_grid.nbytes) / 1e6
    print(f"Total: {total_mb:.0f} MB")

    return {
        "row_a": ROW_A,
        "col_a": COL_A,
        "row_b": ROW_B,
        "col_b": COL_B,
        "pgid_a": PGID_A,
        "pgid_b": PGID_B,
        "ucdp_features": UCDP_FEATURES,
        "acled_features": ACLED_FEATURES,
        "acled_offset": 3,
        "n_months": len(UCDP_MONTHS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic compiled grids for testing"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/synthetic_pipeline"),
    )
    args = parser.parse_args()

    meta = generate(args.output_dir)
    print(f"\nOutput: {args.output_dir}")
    print(f"Cell A: pgid={meta['pgid_a']} (row={meta['row_a']}, col={meta['col_a']})")
    print(f"Cell B: pgid={meta['pgid_b']} (row={meta['row_b']}, col={meta['col_b']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
