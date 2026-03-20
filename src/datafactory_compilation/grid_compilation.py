"""Grid compilation: place event data onto the spatiotemporal grid.

Reads viewpoint output Parquet, assigns each event to a (cell, month) bin,
aggregates using declared strategies, and outputs npy arrays with
sidecar coordinate files and provenance.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from datafactory_compilation.aggregation import get_strategy
from datafactory_compilation.compilation_config import CompilationConfig
from datafactory_priogrid.cell_generator import generate_grid
from datafactory_priogrid.temporal_generator import generate_time_steps
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
)

logger = logging.getLogger(__name__)

DATASET_ID = "compilation"


def _parse_month_index(
    date_str: str,
    start_year: int,
    start_month: int,
) -> int | None:
    """Parse a date string (YYYY-MM-DD) to a 0-based monthly index.

    Returns None if the date is outside the temporal range or malformed.
    """
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


def _place_events(
    events: list[dict],
    config: CompilationConfig,
) -> dict[tuple[int, int], list[dict]]:
    """Assign each event to a (pgid_index, time_index) bin.

    Events outside the grid bounds or temporal range are skipped
    with a warning.

    Returns:
        Dict mapping (pgid_0based_index, time_index) to list of events.
    """
    from datafactory_priogrid.cell_generator import latlon_to_pgid

    bins: dict[tuple[int, int], list[dict]] = defaultdict(list)
    n_skipped_spatial = 0
    n_skipped_temporal = 0

    n_cells = config.grid_config.n_cells
    n_steps = config.temporal_config.n_steps

    for ev in events:
        lat = ev.get(config.lat_field)
        lon = ev.get(config.lon_field)
        date_str = ev.get(config.date_field)

        if lat is None or lon is None:
            n_skipped_spatial += 1
            continue

        try:
            pgid = int(latlon_to_pgid(float(lat), float(lon), config.grid_config))
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

        # pgid is 1-based; convert to 0-based index
        pgid_idx = pgid - 1
        bins[(pgid_idx, time_idx)].append(ev)

    if n_skipped_spatial > 0:
        logger.warning(
            "Skipped %d events: invalid spatial coordinates",
            n_skipped_spatial,
        )
    if n_skipped_temporal > 0:
        logger.warning("Skipped %d events: outside temporal range", n_skipped_temporal)

    logger.info(
        "Placed %d events into %d non-empty bins",
        sum(len(v) for v in bins.values()),
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

    # Compute source digest
    source_digest = compute_content_digest(config.source_path.read_bytes())

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

    # Convert to list of dicts for event processing
    events = table.to_pydict()
    n_rows = table.num_rows
    event_list = [
        {col: events[col][i] for col in events} for i in range(n_rows)
    ]
    logger.info("Read %d events from %s", n_rows, config.source_path)

    # Place events into (cell, month) bins
    bins = _place_events(event_list, config)

    # Build output array
    n_cells = config.grid_config.n_cells
    n_steps = config.temporal_config.n_steps
    n_features = len(config.features)
    grid_array = np.zeros((n_cells, n_steps, n_features), dtype=np.float32)

    # Resolve strategies
    strategies = [get_strategy(feat[1]) for feat in config.features]
    feature_names = [feat[0] for feat in config.features]

    # Aggregate
    for (pgid_idx, time_idx), cell_events in sorted(bins.items()):
        for feat_idx, strategy_fn in enumerate(strategies):
            grid_array[pgid_idx, time_idx, feat_idx] = strategy_fn(cell_events)

    # Generate coordinate arrays
    pgids, _, _ = generate_grid(config.grid_config)
    time_steps = generate_time_steps(config.temporal_config)

    # Write output
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    grid_path = output_dir / "grid.npy"
    np.save(grid_path, grid_array)
    np.save(output_dir / "pgids.npy", pgids)
    np.save(output_dir / "time_steps.npy", time_steps)
    (output_dir / "feature_names.json").write_text(json.dumps(feature_names))

    # Compute output digest
    output_digest = compute_content_digest(grid_path.read_bytes())

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
