"""Grid compilation: place event data onto the spatiotemporal grid.

Reads viewpoint output Parquet, assigns each event to a (cell, month) bin,
aggregates using declared strategies, and outputs npy arrays with
sidecar coordinate files and provenance.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_compilation.aggregation import get_strategy
from datafactory_compilation.compilation_config import CompilationConfig
from datafactory_priogrid.cell_generator import generate_grid
from datafactory_priogrid.temporal_generator import generate_time_steps
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_file_digest,
)

logger = logging.getLogger(__name__)

DATASET_ID = "compilation"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_month_index(
    date_str: str,
    start_year: int,
    start_month: int,
) -> int | None:
    """Parse a date string (YYYY-MM-DD) to a 0-based monthly index.

    Returns None if the date is outside the temporal range or malformed.
    """
    if not _DATE_RE.match(date_str):
        logger.warning("Malformed date string: %r", date_str)
        return None
    try:
        parts = date_str.split("-")
        year = int(parts[0])
        month = int(parts[1])
    except (ValueError, IndexError):
        return None

    if not (1 <= month <= 12):
        return None

    idx = (year - start_year) * 12 + (month - start_month)
    return idx if idx >= 0 else None


def _place_events_columnar(
    table: pa.Table,
    config: CompilationConfig,
) -> dict[tuple[int, int], list[dict]]:
    """Assign events to (pgid_index, time_index) bins using columnar data.

    Extracts only placement columns (lat, lon, date) as lists,
    computes bin assignments, then materializes full event dicts
    only for events that land in valid bins. This avoids creating
    ~19M dict objects upfront for large tables.

    Args:
        table: A PyArrow Table with event data.
        config: Compilation configuration.

    Returns:
        Dict mapping (pgid_0based_index, time_index) to list of events.
    """
    from datafactory_priogrid.cell_generator import latlon_to_pgid

    n_cells = config.grid_config.n_cells
    n_steps = config.temporal_config.n_steps
    n_rows = table.num_rows

    # Extract only placement columns as Python lists
    lats = table[config.lat_field].to_pylist()
    lons = table[config.lon_field].to_pylist()
    dates = table[config.date_field].to_pylist()

    # Phase 1: compute bin assignments (row_index → bin key)
    row_bins: dict[int, tuple[int, int]] = {}
    n_skipped_spatial = 0
    n_skipped_temporal = 0

    for i in range(n_rows):
        lat, lon, date_str = lats[i], lons[i], dates[i]

        if lat is None or lon is None:
            n_skipped_spatial += 1
            continue

        try:
            pgid = int(
                latlon_to_pgid(
                    float(lat), float(lon), config.grid_config
                )
            )
        except (ValueError, TypeError):
            n_skipped_spatial += 1
            continue

        if pgid < 1 or pgid > n_cells:
            n_skipped_spatial += 1
            continue

        if not isinstance(date_str, str):
            n_skipped_temporal += 1
            continue

        time_idx = _parse_month_index(
            date_str,
            config.temporal_config.start_year,
            config.temporal_config.start_month,
        )
        if time_idx is None or time_idx >= n_steps:
            n_skipped_temporal += 1
            continue

        pgid_idx = pgid - 1
        row_bins[i] = (pgid_idx, time_idx)

    if n_skipped_spatial > 0:
        logger.warning(
            "Skipped %d events: invalid spatial coordinates",
            n_skipped_spatial,
        )
    if n_skipped_temporal > 0:
        logger.warning(
            "Skipped %d events: outside temporal range",
            n_skipped_temporal,
        )

    # Phase 2: materialize dicts only for placed events
    if not row_bins:
        logger.info("Placed 0 events into 0 non-empty bins")
        return {}

    # Get all column data as dict-of-lists (one pass)
    col_data = table.to_pydict()
    col_names = list(col_data.keys())

    bins: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for row_idx, bin_key in row_bins.items():
        ev = {col: col_data[col][row_idx] for col in col_names}
        bins[bin_key].append(ev)

    logger.info(
        "Placed %d events into %d non-empty bins",
        len(row_bins),
        len(bins),
    )
    return dict(bins)


def compile_grid(config: CompilationConfig) -> Path:
    """Compile source events onto the spatiotemporal grid.

    Reads the source Parquet, places events onto the grid, aggregates
    using declared strategies, and writes npy output with coordinate
    sidecar files and provenance.

    Args:
        config: Compilation configuration.

    Returns:
        Path to the output directory containing grid.npy and sidecars.

    Raises:
        FileNotFoundError: If source_path does not exist.
        ValueError: If source Parquet lacks required columns.
    """
    # Validate source exists
    if not config.source_path.exists():
        err_msg = f"Source file not found: {config.source_path}"
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    # Compute source digest (chunked to avoid doubling memory)
    source_digest = compute_file_digest(config.source_path)

    # Read source Parquet
    table = pq.read_table(config.source_path)
    required_cols = {config.lat_field, config.lon_field, config.date_field}
    missing_cols = required_cols - set(table.column_names)
    if missing_cols:
        err_msg = (
            f"Source Parquet missing required columns: {sorted(missing_cols)}. "
            f"Available: {sorted(table.column_names)}"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)

    # Place events into (cell, month) bins using columnar extraction.
    # Only placement columns (lat, lon, date) are read as lists;
    # full event dicts are materialized only for placed events.
    logger.info("Read %d events from %s", table.num_rows, config.source_path)
    bins = _place_events_columnar(table, config)

    # Build output array: [T, H, W, C] — canonical z-stack layout
    nrow = config.grid_config.nrow
    ncol = config.grid_config.ncol
    n_steps = config.temporal_config.n_steps
    n_features = len(config.features)
    grid_array = np.zeros(
        (n_steps, nrow, ncol, n_features), dtype=np.float32
    )

    # Resolve strategies
    strategies = [
        get_strategy(feat.strategy) for feat in config.features
    ]
    feature_names = [feat.name for feat in config.features]

    # Aggregate (with optional per-feature filtering)
    for (pgid_idx, time_idx), cell_events in sorted(bins.items()):
        row = pgid_idx // ncol
        col = pgid_idx % ncol
        for feat_idx, (spec, strategy_fn) in enumerate(
            zip(config.features, strategies, strict=True)
        ):
            if spec.filter:
                filtered = [
                    e
                    for e in cell_events
                    if all(
                        e.get(k) == v
                        for k, v in spec.filter.items()
                    )
                ]
            else:
                filtered = cell_events
            grid_array[time_idx, row, col, feat_idx] = (
                strategy_fn(filtered)
            )

    # Generate coordinate arrays
    pgids_flat, _, _ = generate_grid(config.grid_config)
    pgids_2d = pgids_flat.reshape(nrow, ncol)
    time_steps = generate_time_steps(config.temporal_config)

    # Write output
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    grid_path = output_dir / "grid.npy"
    np.save(grid_path, grid_array)
    np.save(output_dir / "pgids.npy", pgids_2d)
    np.save(output_dir / "time_steps.npy", time_steps)
    (output_dir / "feature_names.json").write_text(json.dumps(feature_names))

    # Compute output digest (chunked to avoid doubling memory)
    output_digest = compute_file_digest(grid_path)

    # Write provenance JSON
    provenance = {
        "source_path": str(config.source_path),
        "source_digest": source_digest,
        "grid_shape": list(grid_array.shape),
        "feature_names": feature_names,
        "output_digest": output_digest,
    }
    provenance_path = output_dir / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2))

    # Append to compilation ledger
    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "source_path": str(config.source_path),
        "source_digest": source_digest,
        "grid_shape": list(grid_array.shape),
        "feature_names": feature_names,
        "output_dir": str(output_dir),
        "output_digest": output_digest,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "Compiled grid: shape=%s, features=%s, output=%s",
        grid_array.shape,
        feature_names,
        output_dir,
    )

    return output_dir
