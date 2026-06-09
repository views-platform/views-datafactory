#!/usr/bin/env python3
"""Generate parquet files for training script consumers.

Bridges the data factory output to the format expected by
views-models training scripts (purple_alien, white_ranger, etc.).

These scripts expect parquet files at:
    {model}/data/raw/{run_type}_viewser_df.parquet

With structure:
    - MultiIndex: (month_id, priogrid_gid)
    - Columns: lr_sb_best, lr_ns_best, lr_os_best, c_id, col, row
    - NaN replaced with 0
    - Sorted by index

This script calls load_dataset() from the data factory, renames
columns to match the VIEWSER convention, derives row/col from
priogrid_gid, and saves parquet files for each partition.

Usage:
    uv run python scripts/generate_consumer_data.py
    uv run python scripts/generate_consumer_data.py --output-dir /path/to/model/data/raw
    uv run python scripts/generate_consumer_data.py --partition calibration
    uv run python scripts/generate_consumer_data.py --data-dir <zarr-url>
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG
from datafactory_query.dataset import _is_remote
from datafactory_query.defaults import PARTITIONS as _BASE_PARTITIONS

# ── Consumer contract ──────────────────────────────────────
# These match what purple_alien, white_ranger, and other models
# expect in their config_queryset.py files.

FEATURE_RENAME = {
    "ged_sb_best": "lr_sb_best",
    "ged_ns_best": "lr_ns_best",
    "ged_os_best": "lr_os_best",
    "gaul0_code": "c_id",
}

FACTORY_FEATURES = list(FEATURE_RENAME.keys())

# Calibration/validation from single source of truth; forecasting computed dynamically.
PARTITIONS: dict[str, dict[str, tuple[int, int]] | None] = {
    **_BASE_PARTITIONS,
    "forecasting": None,
}


def _current_month_id() -> int:
    """Current VIEWS month_id."""
    from datetime import date

    today = date.today()
    return (today.year - 1980) * 12 + today.month


def _forecasting_partition(steps: int = 36) -> dict:
    """Compute forecasting partition from current date."""
    month_last = _current_month_id() - 1
    cal_start = _BASE_PARTITIONS["calibration"]["train"][0]
    return {
        "train": (cal_start, month_last),
        "test": (month_last + 1, month_last + 1 + steps),
    }


def _derive_row_col(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Add row and col columns derived from priogrid_gid index.

    PRIO-GRID convention: 1-indexed, ncol columns per row.
    row = (pgid - 1) // ncol + 1
    col = (pgid - 1) % ncol + 1
    """
    ncol = DEFAULT_GRID_CONFIG.ncol
    pgids = df.index.get_level_values("priogrid_gid")
    df = df.copy()
    df["row"] = ((pgids - 1) // ncol + 1).astype(np.float64)
    df["col"] = ((pgids - 1) % ncol + 1).astype(np.float64)
    return df


def generate_partition(
    run_type: str,
    start: int,
    end: int,
    *,
    data_dir: Path | str = Path("data/assembled"),
    gaul_dir: Path = Path("data/raw/gaul_admin"),
    region: str = "land",
) -> pd.DataFrame:
    """Generate a consumer-format DataFrame for one partition.

    Args:
        run_type: Partition name (for logging).
        start: First month_id (inclusive).
        end: Last month_id (inclusive).
        data_dir: Assembled grid path or zarr URL.
        gaul_dir: GAUL admin data path.
        region: Geographic filter.

    Returns:
        DataFrame matching consumer contract.
    """
    from datafactory_query import load_dataset

    df = load_dataset(
        region=region,
        start=start,
        end=end,
        features=FACTORY_FEATURES,
        output_format="dataframe",
        data_dir=data_dir,
        gaul_dir=gaul_dir,
        month_id_epoch=1980,
    )

    # Rename to VIEWSER convention
    df = df.rename(columns=FEATURE_RENAME)

    # Derive row/col from priogrid_gid
    df = _derive_row_col(df)

    # Fill NaN with 0 (matches .transform.missing.replace_na())
    df = df.fillna(0.0)

    # Ensure sorted index
    df = df.sort_index()

    return df


def main() -> int:
    """Generate consumer parquet files."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Generate consumer parquet files from data factory"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: data/consumer/)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/assembled",
        help="Assembled grid path or zarr URL",
    )
    parser.add_argument(
        "--gaul-dir",
        type=Path,
        default=Path("data/raw/gaul_admin"),
        help="GAUL admin data path",
    )
    parser.add_argument(
        "--region",
        default="land",
        help="Geographic filter (default: land)",
    )
    parser.add_argument(
        "--partition",
        choices=["calibration", "validation", "forecasting", "all"],
        default="all",
        help="Which partition to generate (default: all)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=36,
        help="Forecasting horizon in months (default: 36)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or Path("data/consumer")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve partitions
    partitions = dict(PARTITIONS)
    partitions["forecasting"] = _forecasting_partition(args.steps)

    if args.partition != "all":
        partitions = {
            args.partition: partitions[args.partition],
        }

    data_dir: Path | str = args.data_dir
    if not _is_remote(data_dir):
        data_dir = Path(data_dir)

    # Source-digest gate: verify grid.npy matches assembly provenance
    # before generating consumer data. Prevents stale exports (C-254).
    grid_digest: str | None = None
    if not _is_remote(data_dir):
        grid_path = Path(data_dir) / "grid.npy"
        prov_path = Path(data_dir) / "provenance.json"
        if grid_path.exists():
            from datafactory_provenance import compute_file_digest

            print("Computing grid digest (streaming)...")
            grid_digest = compute_file_digest(grid_path)
            print(f"  grid.npy digest: {grid_digest}")
            if prov_path.exists():
                import json

                prov = json.loads(prov_path.read_text())
                recorded = prov.get("output_digest")
                if recorded and recorded != grid_digest:
                    print(
                        f"ABORT: grid.npy digest ({grid_digest}) "
                        f"does not match provenance.json "
                        f"({recorded}). Re-run assembly."
                    )
                    return 1
                if recorded:
                    print(
                        f"  provenance.json digest: {recorded}"
                        f" — MATCH"
                    )

    print("=" * 60)
    print("CONSUMER DATA GENERATOR")
    print(f"Source: {data_dir}")
    print(f"Output: {output_dir}")
    print(f"Region: {args.region}")
    print(f"Partitions: {list(partitions.keys())}")
    print("=" * 60)
    print()

    for run_type, bounds in partitions.items():
        train_start, train_end = bounds["train"]
        test_start, test_end = bounds["test"]

        print(f"── {run_type} ──")

        # Generate full range (train + test)
        full_start = train_start
        full_end = test_end

        t0 = time.monotonic()
        df = generate_partition(
            run_type,
            full_start,
            full_end,
            data_dir=data_dir,
            gaul_dir=args.gaul_dir,
            region=args.region,
        )
        elapsed = time.monotonic() - t0

        out_path = output_dir / f"{run_type}_viewser_df.parquet"
        df.to_parquet(out_path)

        print(f"  Months: {full_start}-{full_end}")
        print(f"  Shape: {df.shape}")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Output: {out_path}")
        print(f"  Size: {out_path.stat().st_size / 1e6:.1f} MB")
        print(f"  Time: {elapsed:.1f}s")
        print()

    # Write provenance manifest (C-254)
    import json
    from datetime import UTC, datetime

    manifest: dict = {
        "generation_timestamp": datetime.now(tz=UTC).isoformat(),
        "source_grid_digest": grid_digest,
        "feature_mapping": FEATURE_RENAME,
        "output_files": {},
    }
    for name in partitions:
        pq_path = output_dir / f"{name}_viewser_df.parquet"
        if pq_path.exists():
            from datafactory_provenance import compute_file_digest

            manifest["output_files"][str(pq_path)] = (
                compute_file_digest(pq_path)
            )

    manifest_path = output_dir / "provenance.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Provenance manifest: {manifest_path}")

    # Clear assembly sentinel if present
    if not _is_remote(data_dir):
        sentinel = Path(data_dir) / ".exports_required"
        if sentinel.exists():
            sentinel.unlink()
            print("Cleared .exports_required sentinel")

    print("=" * 60)
    print("DONE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
