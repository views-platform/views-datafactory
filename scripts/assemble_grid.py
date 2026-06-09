#!/usr/bin/env python3
"""Assemble a canonical [T, H, W, F] grid from all data sources.

Usage:
    uv run python scripts/assemble_grid.py
    uv run python scripts/assemble_grid.py --acled-grid data/compiled/acled
    uv run python scripts/assemble_grid.py --ghspop-grid data/compiled/ghspop
    uv run python scripts/assemble_grid.py --ghsbuilts-grid data/compiled/ghsbuilts
    uv run python scripts/assemble_grid.py --admin-dir data/gaul_admin

Combines the compiled UCDP conflict grid, ACLED conflict grid,
GHS-POP population grid, GHS-BUILT-S built-up surface grid, V-Dem
democracy indicators, PRIO-GRID static features, and GAUL admin
boundary codes into a single array. ACLED, GHS-POP, GHS-BUILT-S,
and V-Dem are temporally aligned to the UCDP timeline and zero-filled
outside their coverage range. Static and admin features are broadcast
across all time steps.

Output: grid.npy [T, H, W, F]
        F = UCDP + ACLED + GHS-POP + GHS-BUILT-S + V-Dem + static + admin.

Admin channels (gaul0_code, gaul1_code, gaul2_code) are categorical
integers stored as float32. Downstream models should treat them as
categorical (embedding / one-hot), not continuous.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import numpy as np

from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG


@dataclass(frozen=True)
class AssemblyConfig:
    """Configuration for grid assembly (ADR-009).

    Declares all input sources, output destination, and the set of
    admin boundary fields that become grid channels. Argparse
    provides CLI overrides; this dataclass validates at entry.
    """

    ucdp_grid_dir: Path = Path("data/compiled")
    acled_grid_dir: Path | None = None
    ghspop_grid_dir: Path | None = None
    ghsbuilts_grid_dir: Path | None = None
    vdem_grid_dir: Path | None = None
    static_dir: Path = Path("data/raw/priogrid_static")
    admin_dir: Path = Path("data/raw/gaul_admin")
    output_dir: Path = Path("data/assembled")

    admin_numeric_fields: tuple[str, ...] = (
        "gaul0_code", "gaul1_code", "gaul2_code",
    )
    admin_fill_value: float = -1.0
    output_dtype: str = "float32"
    disk_space_margin: float = 1.2

    _ALLOWED_DTYPES: ClassVar[frozenset[str]] = frozenset({
        "float16", "float32", "float64",
    })

    def __post_init__(self) -> None:
        if not self.admin_numeric_fields:
            msg = "admin_numeric_fields must be non-empty"
            raise ValueError(msg)
        if len(self.admin_numeric_fields) != len(
            set(self.admin_numeric_fields)
        ):
            msg = "duplicate admin_numeric_fields"
            raise ValueError(msg)
        if self.output_dtype not in self._ALLOWED_DTYPES:
            msg = (
                f"output_dtype must be one of "
                f"{sorted(self._ALLOWED_DTYPES)}, "
                f"got {self.output_dtype!r}"
            )
            raise ValueError(msg)
        if self.disk_space_margin < 1.0:
            msg = (
                f"disk_space_margin must be >= 1.0, "
                f"got {self.disk_space_margin}"
            )
            raise ValueError(msg)


def _load_source_grid(
    name: str,
    grid_dir: Path,
    time_steps: np.ndarray,
    n_t: int,
) -> tuple[np.ndarray, list[str], int] | None:
    """Load, validate, and align a compiled source grid."""
    grid_path = grid_dir / "grid.npy"
    feat_path = grid_dir / "feature_names.json"
    time_path = grid_dir / "time_steps.npy"
    for p in (grid_path, feat_path, time_path):
        if not p.exists():
            print(f"FAIL: {p} not found")
            return None

    grid = np.load(grid_path, mmap_mode="r")
    features = json.loads(feat_path.read_text())
    source_time_steps = np.load(time_path)
    DEFAULT_GRID_CONFIG.assert_grid_shape(grid)

    start_dt = source_time_steps[0]
    matches = np.where(time_steps == start_dt)[0]
    if len(matches) != 1:
        print(
            f"FAIL: {name} start {start_dt} not found "
            f"in UCDP timeline (or ambiguous)"
        )
        return None
    offset = int(matches[0])
    n_source_t = grid.shape[0]
    end_idx = offset + n_source_t
    if end_idx > n_t:
        print(
            f"FAIL: {name} extends beyond UCDP timeline "
            f"(offset {offset} + {n_source_t} > {n_t})"
        )
        return None

    n_features = len(features)
    print(
        f"{name} grid: [T={n_source_t}, "
        f"H={grid.shape[1]}, W={grid.shape[2]}, "
        f"C={n_features}]"
    )
    print(f"{name} features: {features}")
    print(
        f"{name} temporal alignment: indices "
        f"{offset}-{end_idx - 1} in assembled grid"
    )
    if offset > 0 or end_idx < n_t:
        print(
            f"  Zero-fill: 0-{offset - 1}, "
            f"{end_idx}-{n_t - 1}"
        )
    return grid, features, offset


def _composite_parquet_digest(directory: Path) -> str | None:
    """SHA-256 digest of sorted Parquet files in *directory*."""
    from datafactory_provenance import compute_content_digest, compute_file_digest

    files = sorted(directory.glob("*.parquet"))
    if not files:
        return None
    return compute_content_digest(
        b"|".join(compute_file_digest(f).encode() for f in files)
    )


def main() -> int:
    """Assemble the canonical grid."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    defaults = AssemblyConfig()

    parser = argparse.ArgumentParser(
        description="Assemble canonical grid from all sources"
    )
    parser.add_argument(
        "--ucdp-grid",
        type=Path,
        default=defaults.ucdp_grid_dir,
        help="Compiled UCDP grid directory",
    )
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=defaults.static_dir,
        help="PRIO-GRID static Parquet directory",
    )
    parser.add_argument(
        "--admin-dir",
        type=Path,
        default=defaults.admin_dir,
        help="GAUL admin boundary Parquet directory",
    )
    parser.add_argument(
        "--acled-grid",
        type=Path,
        default=None,
        help="Compiled ACLED grid directory (omit to skip ACLED)",
    )
    parser.add_argument(
        "--ghspop-grid",
        type=Path,
        default=None,
        help="Compiled GHS-POP grid directory (omit to skip GHS-POP)",
    )
    parser.add_argument(
        "--ghsbuilts-grid",
        type=Path,
        default=None,
        help=(
            "Compiled GHS-BUILT-S grid directory "
            "(omit to skip GHS-BUILT-S)"
        ),
    )
    parser.add_argument(
        "--vdem-grid",
        type=Path,
        default=None,
        help=(
            "Compiled V-Dem grid directory "
            "(omit to skip V-Dem)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=defaults.output_dir,
        help="Output directory",
    )
    parser.add_argument(
        "--skip-if-unchanged",
        action="store_true",
        help=(
            "Skip assembly if all input source digests match "
            "the previous provenance.json"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild, bypassing content-addressed skip",
    )
    args = parser.parse_args()

    config = AssemblyConfig(
        ucdp_grid_dir=args.ucdp_grid,
        acled_grid_dir=args.acled_grid,
        ghspop_grid_dir=args.ghspop_grid,
        ghsbuilts_grid_dir=args.ghsbuilts_grid,
        vdem_grid_dir=args.vdem_grid,
        static_dir=args.static_dir,
        admin_dir=args.admin_dir,
        output_dir=args.output_dir,
    )

    # Validate inputs
    grid_path = config.ucdp_grid_dir / "grid.npy"
    pgids_path = config.ucdp_grid_dir / "pgids.npy"
    time_path = config.ucdp_grid_dir / "time_steps.npy"
    features_path = config.ucdp_grid_dir / "feature_names.json"

    for p in [grid_path, pgids_path, time_path, features_path]:
        if not p.exists():
            print(f"FAIL: {p} not found")
            return 1

    if not config.static_dir.exists():
        print(f"FAIL: {config.static_dir} not found")
        return 1

    has_admin = config.admin_dir.exists()
    if not has_admin:
        print(
            f"NOTE: {config.admin_dir} not found, "
            "skipping admin channels"
        )

    has_acled = config.acled_grid_dir is not None
    if has_acled and not config.acled_grid_dir.exists():
        print(
            f"FAIL: --acled-grid {config.acled_grid_dir} "
            "not found"
        )
        return 1

    has_ghspop = config.ghspop_grid_dir is not None
    if has_ghspop and not config.ghspop_grid_dir.exists():
        print(
            f"FAIL: --ghspop-grid {config.ghspop_grid_dir} "
            "not found"
        )
        return 1

    has_ghsbuilts = config.ghsbuilts_grid_dir is not None
    if has_ghsbuilts and not config.ghsbuilts_grid_dir.exists():
        print(
            f"FAIL: --ghsbuilts-grid "
            f"{config.ghsbuilts_grid_dir} not found"
        )
        return 1

    has_vdem = config.vdem_grid_dir is not None
    if has_vdem and not config.vdem_grid_dir.exists():
        print(
            f"FAIL: --vdem-grid "
            f"{config.vdem_grid_dir} not found"
        )
        return 1

    print("=" * 60)
    print("GRID ASSEMBLY — All Data Sources")
    print(f"UCDP grid:   {config.ucdp_grid_dir}")
    print(f"ACLED grid:  "
          f"{config.acled_grid_dir if has_acled else '(skipped)'}")
    print(f"GHS-POP grid: "
          f"{config.ghspop_grid_dir if has_ghspop else '(skipped)'}")
    print(f"GHS-BUILT-S grid: "
          f"{config.ghsbuilts_grid_dir if has_ghsbuilts else '(skipped)'}")
    print(f"V-Dem grid:  "
          f"{config.vdem_grid_dir if has_vdem else '(skipped)'}")
    print(f"Static dir:  {config.static_dir}")
    print(f"Admin dir:   {config.admin_dir}"
          f"{'' if has_admin else ' (skipped)'}")
    print(f"Output:      {config.output_dir}")
    print("=" * 60)
    print()

    # Content-addressed skip (ADR-041): compare input digests against
    # previous run, verify output integrity, record outcome in ledger.
    if args.skip_if_unchanged and not args.force:
        prov_path = config.output_dir / "provenance.json"
        output_grid = config.output_dir / "grid.npy"

        from datafactory_provenance import (
            DIGEST_SCHEME,
            LEDGER_VERSION,
            append_ledger_entry,
            check_assembly_skip,
            compute_file_digest,
        )

        current_digests = {
            "ucdp_digest": compute_file_digest(
                config.ucdp_grid_dir / "grid.npy"
            ),
        }
        if has_acled:
            current_digests["acled_digest"] = compute_file_digest(
                config.acled_grid_dir / "grid.npy"
            )
        if has_ghspop:
            current_digests["ghspop_digest"] = compute_file_digest(
                config.ghspop_grid_dir / "grid.npy"
            )
        if has_ghsbuilts:
            current_digests["ghsbuilts_digest"] = compute_file_digest(
                config.ghsbuilts_grid_dir / "grid.npy"
            )
        if has_vdem:
            current_digests["vdem_digest"] = compute_file_digest(
                config.vdem_grid_dir / "grid.npy"
            )

        static_digest = _composite_parquet_digest(config.static_dir)
        if static_digest is not None:
            current_digests["static_digest"] = static_digest

        if has_admin:
            admin_digest = _composite_parquet_digest(config.admin_dir)
            if admin_digest is not None:
                current_digests["admin_digest"] = admin_digest

        verdict = check_assembly_skip(
            current_digests, prov_path, output_grid,
        )

        if verdict.should_skip:
            print("SKIP: all input digests match previous assembly")
            for k, v in current_digests.items():
                print(f"  {k}: {v}")
            print(f"Output unchanged: {output_grid}")
            ledger_path = config.output_dir / "ledger.jsonl"
            append_ledger_entry(ledger_path, {
                "stage": "assembly",
                "outcome": "unchanged",
                "input_digests": current_digests,
                "ledger_version": LEDGER_VERSION,
                "digest_algorithm": DIGEST_SCHEME,
            })
            print("PASS")
            return 0
        else:
            print(f"Input changed: {verdict.reason} — rebuilding")

    from datafactory_provenance import (
        DIGEST_SCHEME,
        LEDGER_VERSION,
        append_ledger_entry,
        compute_file_digest,
    )
    _ledger_path = config.output_dir / "ledger.jsonl"

    def _write_failed_entry() -> None:
        with contextlib.suppress(Exception):
            append_ledger_entry(_ledger_path, {
                "stage": "assembly",
                "outcome": "failed",
                "ledger_version": LEDGER_VERSION,
                "digest_algorithm": DIGEST_SCHEME,
            })

    import pyarrow.parquet as pq

    t0 = time.monotonic()

    # Load UCDP grid (mmap to reduce peak memory)
    ucdp_grid = np.load(grid_path, mmap_mode="r")
    pgids = np.load(pgids_path)
    time_steps = np.load(time_path)
    ucdp_features = json.loads(features_path.read_text())

    DEFAULT_GRID_CONFIG.assert_grid_shape(ucdp_grid)
    n_t, n_h, n_w, n_ucdp = ucdp_grid.shape
    print(
        f"UCDP grid: [T={n_t}, H={n_h}, W={n_w}, "
        f"C={n_ucdp}]"
    )
    print(f"UCDP features: {ucdp_features}")

    if has_acled:
        acled_result = _load_source_grid(
            "ACLED", config.acled_grid_dir, time_steps, n_t,
        )
        if acled_result is None:
            _write_failed_entry()
            return 1
        acled_grid, acled_features, acled_offset = acled_result
    else:
        acled_grid, acled_features, acled_offset = None, [], 0
    n_acled = len(acled_features)

    if has_ghspop:
        ghspop_result = _load_source_grid(
            "GHS-POP", config.ghspop_grid_dir, time_steps, n_t,
        )
        if ghspop_result is None:
            _write_failed_entry()
            return 1
        ghspop_grid, ghspop_features, ghspop_offset = ghspop_result
    else:
        ghspop_grid, ghspop_features, ghspop_offset = None, [], 0
    n_ghspop = len(ghspop_features)

    if has_ghsbuilts:
        ghsbuilts_result = _load_source_grid(
            "GHS-BUILT-S", config.ghsbuilts_grid_dir,
            time_steps, n_t,
        )
        if ghsbuilts_result is None:
            _write_failed_entry()
            return 1
        ghsbuilts_grid, ghsbuilts_features, ghsbuilts_offset = (
            ghsbuilts_result
        )
    else:
        ghsbuilts_grid, ghsbuilts_features, ghsbuilts_offset = (
            None, [], 0,
        )
    n_ghsbuilts = len(ghsbuilts_features)

    if has_vdem:
        vdem_result = _load_source_grid(
            "V-Dem", config.vdem_grid_dir,
            time_steps, n_t,
        )
        if vdem_result is None:
            _write_failed_entry()
            return 1
        vdem_grid, vdem_features, vdem_offset = vdem_result
    else:
        vdem_grid, vdem_features, vdem_offset = None, [], 0
    n_vdem = len(vdem_features)

    # Build gid → (row, col) lookup from pgids array
    gid_to_rowcol: dict[int, tuple[int, int]] = {}
    for r in range(n_h):
        for c in range(n_w):
            gid_to_rowcol[int(pgids[r, c])] = (r, c)

    # Discover and sort static variable files
    static_files = sorted(config.static_dir.glob("*.parquet"))
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
            (n_h, n_w), dtype=np.dtype(config.output_dtype),
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
    admin_names: list[str] = []
    admin_spatial: list[np.ndarray] = []

    if has_admin:
        admin_files = sorted(config.admin_dir.glob("*.parquet"))
        print(f"Admin variables: {len(admin_files)}")

        for af in admin_files:
            var_name = af.stem
            if var_name not in config.admin_numeric_fields:
                continue

            table = pq.read_table(af)
            gids = table.column("gid").to_pylist()
            values = table.column("value").to_pylist()

            spatial = np.full(
                (n_h, n_w),
                config.admin_fill_value,
                dtype=np.dtype(config.output_dtype),
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
    n_total = (
        n_ucdp + n_acled + n_ghspop + n_ghsbuilts
        + n_vdem + n_static + n_admin
    )
    all_features = (
        ucdp_features + acled_features + ghspop_features
        + ghsbuilts_features + vdem_features
        + static_names + admin_names
    )

    print(
        f"Assembling [T={n_t}, H={n_h}, "
        f"W={n_w}, F={n_total}]..."
    )
    dtype = np.dtype(config.output_dtype)
    bytes_per_element = dtype.itemsize
    print(
        f"  Size: "
        f"{n_t * n_h * n_w * n_total * bytes_per_element / 1e9:.1f} GB"
    )

    # Allocate output as memory-mapped file to avoid OOM on
    # servers with limited RAM. Writes go directly to disk;
    # peak memory is ~150 MB instead of 4.6 GB.
    config.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = config.output_dir / "grid.npy"
    tmp_path = config.output_dir / "grid.npy.tmp"

    # Pre-flight disk space check (C-105)
    expected_bytes = (
        n_t * n_h * n_w * n_total * bytes_per_element
    )
    free_bytes = shutil.disk_usage(config.output_dir).free
    if free_bytes < expected_bytes * config.disk_space_margin:
        margin = config.disk_space_margin
        print(
            f"FAIL: insufficient disk space "
            f"({free_bytes / 1e9:.1f} GB free, "
            f"need {expected_bytes * margin / 1e9:.1f} GB)"
        )
        _write_failed_entry()
        return 1

    try:
        assembled = np.lib.format.open_memmap(
            str(tmp_path),
            mode="w+",
            dtype=dtype,
            shape=(n_t, n_h, n_w, n_total),
        )

        # Copy UCDP channels
        assembled[:, :, :, :n_ucdp] = ucdp_grid
        del ucdp_grid  # free memory

        # Copy ACLED channels (temporal slice, rest stays zero)
        if acled_grid is not None:
            acled_end = acled_offset + acled_grid.shape[0]
            assembled[
                acled_offset:acled_end,
                :, :,
                n_ucdp:n_ucdp + n_acled,
            ] = acled_grid
            del acled_grid

        # Copy GHS-POP channels (temporal slice, rest stays zero)
        if ghspop_grid is not None:
            ghspop_end = ghspop_offset + ghspop_grid.shape[0]
            ch_ghspop = n_ucdp + n_acled
            assembled[
                ghspop_offset:ghspop_end,
                :, :,
                ch_ghspop:ch_ghspop + n_ghspop,
            ] = ghspop_grid
            del ghspop_grid

        # Copy GHS-BUILT-S channels (temporal slice, rest stays zero)
        if ghsbuilts_grid is not None:
            ghsbuilts_end = (
                ghsbuilts_offset + ghsbuilts_grid.shape[0]
            )
            ch_ghsbuilts = n_ucdp + n_acled + n_ghspop
            assembled[
                ghsbuilts_offset:ghsbuilts_end,
                :, :,
                ch_ghsbuilts:ch_ghsbuilts + n_ghsbuilts,
            ] = ghsbuilts_grid
            del ghsbuilts_grid

        # Copy V-Dem channels (temporal slice, rest stays zero)
        if vdem_grid is not None:
            vdem_end = vdem_offset + vdem_grid.shape[0]
            ch_vdem = (
                n_ucdp + n_acled + n_ghspop + n_ghsbuilts
            )
            assembled[
                vdem_offset:vdem_end,
                :, :,
                ch_vdem:ch_vdem + n_vdem,
            ] = vdem_grid
            del vdem_grid

        # Fill static channels (broadcast in-place)
        ch_static = (
            n_ucdp + n_acled + n_ghspop + n_ghsbuilts + n_vdem
        )
        for i, spatial in enumerate(static_spatial):
            assembled[:, :, :, ch_static + i] = spatial

        del static_spatial  # free memory

        # Fill admin channels (broadcast in-place)
        ch_admin = ch_static + n_static
        for i, spatial in enumerate(admin_spatial):
            assembled[:, :, :, ch_admin + i] = spatial

        del admin_spatial  # free memory

        print(f"Assembled shape: {assembled.shape}")
        print(f"  [T={assembled.shape[0]}, "
              f"H={assembled.shape[1]}, "
              f"W={assembled.shape[2]}, "
              f"F={assembled.shape[3]}]")
        print(f"Features ({len(all_features)}):")
        for i, name in enumerate(all_features):
            print(f"  {i:2d}: {name}")

        # Flush mmap to disk, then atomic rename (C-105)
        assembled.flush()
        del assembled  # release mmap before rename
        os.rename(str(tmp_path), str(output_path))
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        _write_failed_entry()
        raise
    np.save(config.output_dir / "pgids.npy", pgids)
    np.save(config.output_dir / "time_steps.npy", time_steps)
    (config.output_dir / "feature_names.json").write_text(
        json.dumps(all_features)
    )

    # Provenance
    output_digest = compute_file_digest(
        config.output_dir / "grid.npy"
    )
    ucdp_digest = compute_file_digest(grid_path)
    acled_digest = (
        compute_file_digest(config.acled_grid_dir / "grid.npy")
        if has_acled else None
    )
    ghspop_digest = (
        compute_file_digest(config.ghspop_grid_dir / "grid.npy")
        if has_ghspop else None
    )
    ghsbuilts_digest = (
        compute_file_digest(config.ghsbuilts_grid_dir / "grid.npy")
        if has_ghsbuilts else None
    )
    vdem_digest = (
        compute_file_digest(config.vdem_grid_dir / "grid.npy")
        if has_vdem else None
    )

    static_digest = _composite_parquet_digest(config.static_dir)
    admin_digest = (
        _composite_parquet_digest(config.admin_dir)
        if has_admin else None
    )

    # Data boundaries
    from datafactory_priogrid import to_views_month_id

    ucdp_grid_ro = np.load(grid_path, mmap_mode="r")
    has_data = ucdp_grid_ro.sum(axis=(1, 2, 3)) > 0
    valid_steps = np.where(has_data)[0]
    last_valid_month_id: int | None = None
    if len(valid_steps) > 0:
        last_idx = int(valid_steps[-1])
        last_dt = time_steps[last_idx]
        last_valid_month_id = int(to_views_month_id(last_dt))
        print(
            f"Last valid UCDP month: {last_valid_month_id} "
            f"({last_dt})"
        )
    del ucdp_grid_ro

    # ACLED data boundary
    last_valid_acled_month_id: int | None = None
    if has_acled:
        acled_grid_ro = np.load(
            config.acled_grid_dir / "grid.npy", mmap_mode="r",
        )
        acled_ts = np.load(config.acled_grid_dir / "time_steps.npy")
        acled_has_data = acled_grid_ro.sum(axis=(1, 2, 3)) > 0
        acled_valid = np.where(acled_has_data)[0]
        if len(acled_valid) > 0:
            acled_last = int(acled_valid[-1])
            acled_last_dt = acled_ts[acled_last]
            last_valid_acled_month_id = int(
                to_views_month_id(acled_last_dt)
            )
            print(
                f"Last valid ACLED month: "
                f"{last_valid_acled_month_id} ({acled_last_dt})"
            )
        del acled_grid_ro

    # GHS-POP data boundary
    last_valid_ghspop_month_id: int | None = None
    if has_ghspop:
        ghspop_grid_ro = np.load(
            config.ghspop_grid_dir / "grid.npy", mmap_mode="r",
        )
        ghspop_ts = np.load(
            config.ghspop_grid_dir / "time_steps.npy",
        )
        ghspop_has_data = ghspop_grid_ro.sum(axis=(1, 2, 3)) > 0
        ghspop_valid = np.where(ghspop_has_data)[0]
        if len(ghspop_valid) > 0:
            ghspop_last = int(ghspop_valid[-1])
            ghspop_last_dt = ghspop_ts[ghspop_last]
            last_valid_ghspop_month_id = int(
                to_views_month_id(ghspop_last_dt)
            )
            print(
                f"Last valid GHS-POP month: "
                f"{last_valid_ghspop_month_id} "
                f"({ghspop_last_dt})"
            )
        del ghspop_grid_ro

    # GHS-BUILT-S data boundary
    last_valid_ghsbuilts_month_id: int | None = None
    if has_ghsbuilts:
        ghsbuilts_grid_ro = np.load(
            config.ghsbuilts_grid_dir / "grid.npy",
            mmap_mode="r",
        )
        ghsbuilts_ts = np.load(
            config.ghsbuilts_grid_dir / "time_steps.npy",
        )
        ghsbuilts_has_data = (
            ghsbuilts_grid_ro.sum(axis=(1, 2, 3)) > 0
        )
        ghsbuilts_valid = np.where(ghsbuilts_has_data)[0]
        if len(ghsbuilts_valid) > 0:
            ghsbuilts_last = int(ghsbuilts_valid[-1])
            ghsbuilts_last_dt = ghsbuilts_ts[ghsbuilts_last]
            last_valid_ghsbuilts_month_id = int(
                to_views_month_id(ghsbuilts_last_dt)
            )
            print(
                f"Last valid GHS-BUILT-S month: "
                f"{last_valid_ghsbuilts_month_id} "
                f"({ghsbuilts_last_dt})"
            )
        del ghsbuilts_grid_ro

    # V-Dem data boundary
    last_valid_vdem_month_id: int | None = None
    if has_vdem:
        vdem_grid_ro = np.load(
            config.vdem_grid_dir / "grid.npy",
            mmap_mode="r",
        )
        vdem_ts = np.load(
            config.vdem_grid_dir / "time_steps.npy",
        )
        vdem_has_data = np.nansum(vdem_grid_ro, axis=(1, 2, 3)) > 0
        vdem_valid = np.where(vdem_has_data)[0]
        if len(vdem_valid) > 0:
            vdem_last = int(vdem_valid[-1])
            vdem_last_dt = vdem_ts[vdem_last]
            last_valid_vdem_month_id = int(
                to_views_month_id(vdem_last_dt)
            )
            print(
                f"Last valid V-Dem month: "
                f"{last_valid_vdem_month_id} "
                f"({vdem_last_dt})"
            )
        del vdem_grid_ro

    provenance = {
        "sources": {
            "ucdp_grid": str(grid_path),
            "ucdp_digest": ucdp_digest,
            "acled_grid": (
                str(config.acled_grid_dir / "grid.npy")
                if has_acled else None
            ),
            "acled_digest": acled_digest,
            "acled_features": acled_features or None,
            "acled_temporal_offset": (
                acled_offset if has_acled else None
            ),
            "ghspop_grid": (
                str(config.ghspop_grid_dir / "grid.npy")
                if has_ghspop else None
            ),
            "ghspop_digest": ghspop_digest,
            "ghspop_features": ghspop_features or None,
            "ghspop_temporal_offset": (
                ghspop_offset if has_ghspop else None
            ),
            "ghsbuilts_grid": (
                str(config.ghsbuilts_grid_dir / "grid.npy")
                if has_ghsbuilts else None
            ),
            "ghsbuilts_digest": ghsbuilts_digest,
            "ghsbuilts_features": ghsbuilts_features or None,
            "ghsbuilts_temporal_offset": (
                ghsbuilts_offset if has_ghsbuilts else None
            ),
            "vdem_grid": (
                str(config.vdem_grid_dir / "grid.npy")
                if has_vdem else None
            ),
            "vdem_digest": vdem_digest,
            "vdem_features": vdem_features or None,
            "vdem_temporal_offset": (
                vdem_offset if has_vdem else None
            ),
            "static_dir": str(config.static_dir),
            "static_digest": static_digest,
            "static_variables": static_names,
            "admin_dir": str(config.admin_dir),
            "admin_digest": admin_digest,
            "admin_variables": admin_names,
        },
        "output_shape": [n_t, n_h, n_w, n_total],
        "n_features": len(all_features),
        "feature_names": all_features,
        "output_digest": output_digest,
    }
    if last_valid_month_id is not None:
        provenance["last_valid_month_id"] = last_valid_month_id
    if last_valid_acled_month_id is not None:
        provenance["last_valid_acled_month_id"] = (
            last_valid_acled_month_id
        )
    if last_valid_ghspop_month_id is not None:
        provenance["last_valid_ghspop_month_id"] = (
            last_valid_ghspop_month_id
        )
    if last_valid_ghsbuilts_month_id is not None:
        provenance["last_valid_ghsbuilts_month_id"] = (
            last_valid_ghsbuilts_month_id
        )
    if last_valid_vdem_month_id is not None:
        provenance["last_valid_vdem_month_id"] = (
            last_valid_vdem_month_id
        )
    (config.output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2)
    )

    input_digests = {
        k: v for k, v in provenance["sources"].items()
        if k.endswith("_digest") and v is not None
    }
    append_ledger_entry(config.output_dir / "ledger.jsonl", {
        "stage": "assembly",
        "outcome": "success",
        "output_digest": output_digest,
        "input_digests": input_digests,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    # Signal that derived artifacts (zarr, consumer parquet) need
    # re-export. Export scripts clear this after success (C-253).
    sentinel = config.output_dir / ".exports_required"
    sentinel.write_text(json.dumps({
        "grid_digest": output_digest,
        "assembled_at": provenance.get(
            "assembled_at",
            datetime.now(tz=UTC).isoformat(),
        ),
    }))

    elapsed = time.monotonic() - t0
    size_gb = (config.output_dir / "grid.npy").stat().st_size / 1e9
    print()
    print(f"Output: {config.output_dir / 'grid.npy'}")
    print(f"Size: {size_gb:.1f} GB")
    print(f"Digest: {output_digest}")
    print(f"Time: {elapsed:.1f}s")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
