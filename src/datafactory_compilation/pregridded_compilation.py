"""Pre-gridded compilation: place pre-gridded data onto the spatiotemporal grid.

Reads viewpoint output Parquet with (pgid, month_id, value) rows,
places values directly into [T, H, W, C] npy arrays. No lat/lon
lookup or event aggregation — the viewpoint has already resolved
spatial and temporal coordinates.

Produces the same output format as compile_grid(): grid.npy,
pgids.npy, time_steps.npy, feature_names.json, provenance.json,
and a ledger entry.

Ref: ADR-024 (grid invariants), ADR-029 (GHS-POP source).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import numpy as np
import pyarrow.parquet as pq

from datafactory_compilation.output import write_compilation_output
from datafactory_priogrid.cell_generator import generate_grid
from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG, GridConfig
from datafactory_priogrid.temporal_config import TemporalConfig
from datafactory_priogrid.temporal_generator import (
    DEFAULT_TEMPORAL_CONFIG,
    generate_time_steps,
)
from datafactory_provenance import VIEWS_EPOCH_YEAR, compute_file_digest

logger = logging.getLogger(__name__)

DATASET_ID = "pregridded_compilation"


@dataclass(frozen=True)
class PregriddedFeatureSpec:
    """A single pre-gridded feature: output name and source column."""

    name: str
    value_field: str


@dataclass(frozen=True)
class PregriddedCompilationConfig:
    """Configuration for compiling pre-gridded viewpoint output onto the grid.

    Unlike CompilationConfig, this expects source data already keyed by
    (pgid, month_id) — no lat/lon lookup or aggregation strategies.
    """

    source_path: Path

    grid_config: GridConfig = field(
        default_factory=lambda: DEFAULT_GRID_CONFIG
    )
    temporal_config: TemporalConfig = field(
        default_factory=lambda: DEFAULT_TEMPORAL_CONFIG
    )

    features: tuple[PregriddedFeatureSpec, ...] = ()

    output_dir: Path = Path("data/compiled")
    ledger_path: Path = Path(
        "provenance/compiler/pregridded_compilation_ledger.jsonl"
    )

    pgid_field: str = "pgid"
    month_id_field: str = "month_id"

    output_dtype: str = "float32"
    fill_value: float = 0.0

    _ALLOWED_DTYPES: ClassVar[frozenset[str]] = frozenset({
        "float16", "float32", "float64", "int32", "int64",
    })

    def __post_init__(self) -> None:
        if not self.features:
            err_msg = "features must be non-empty"
            logger.error(err_msg)
            raise ValueError(err_msg)
        names = [f.name for f in self.features]
        if len(names) != len(set(names)):
            dupes = sorted({n for n in names if names.count(n) > 1})
            err_msg = f"duplicate feature names: {dupes}"
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.output_dtype not in self._ALLOWED_DTYPES:
            err_msg = (
                f"output_dtype must be one of "
                f"{sorted(self._ALLOWED_DTYPES)}, "
                f"got {self.output_dtype!r}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)


def _month_id_to_time_index(
    month_id: int,
    start_year: int,
    start_month: int,
) -> int:
    """Convert VIEWS month_id to 0-based time index.

    VIEWS month_id: 1 = January 1980.
    Time index 0 = start_year/start_month from TemporalConfig.
    """
    year = VIEWS_EPOCH_YEAR + (month_id - 1) // 12
    month = (month_id - 1) % 12 + 1
    return (year - start_year) * 12 + (month - start_month)


def compile_pregridded(config: PregriddedCompilationConfig) -> Path:
    """Compile pre-gridded viewpoint output onto the spatiotemporal grid.

    Reads Parquet with (pgid, month_id, value_columns), converts pgid
    to (row, col) and month_id to time_index, and places values into
    [T, H, W, C] npy output.

    Args:
        config: Pre-gridded compilation configuration.

    Returns:
        Path to the output directory containing grid.npy and sidecars.

    Raises:
        FileNotFoundError: If source_path does not exist.
        ValueError: If source Parquet lacks required columns.
    """
    if not config.source_path.exists():
        err_msg = f"Source file not found: {config.source_path}"
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    source_digest = compute_file_digest(config.source_path)

    needed_cols = {config.pgid_field, config.month_id_field}
    for feat in config.features:
        needed_cols.add(feat.value_field)

    available_cols = set(pq.read_schema(config.source_path).names)
    missing_cols = needed_cols - available_cols
    if missing_cols:
        err_msg = (
            f"Source Parquet missing required columns: "
            f"{sorted(missing_cols)}. "
            f"Available: {sorted(available_cols)}"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)

    table = pq.read_table(
        config.source_path, columns=sorted(needed_cols)
    )
    logger.info(
        "Read %d rows from %s", table.num_rows, config.source_path
    )

    nrow = config.grid_config.nrow
    ncol = config.grid_config.ncol
    n_cells = config.grid_config.n_cells
    n_steps = config.temporal_config.n_steps
    n_features = len(config.features)
    dtype = np.dtype(config.output_dtype)

    # Pre-flight disk space check (C-223 / ADR-037)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    required_bytes = (
        n_steps * nrow * ncol * n_features * dtype.itemsize
    )
    free_bytes = shutil.disk_usage(config.output_dir).free
    if free_bytes < required_bytes * 1.2:
        err_msg = (
            f"Insufficient disk space: "
            f"need {required_bytes * 1.2 / 1e9:.1f} GB, "
            f"have {free_bytes / 1e9:.1f} GB free"
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    # Allocate grid as memory-mapped file (ADR-037).
    # OS pages data in/out as needed — peak RSS stays bounded
    # regardless of feature count.
    tmp_fd, tmp_mmap_path = tempfile.mkstemp(
        prefix="_memmap_", suffix=".npy",
        dir=str(config.output_dir),
    )
    os.close(tmp_fd)

    grid_array = None
    try:
        grid_array = np.lib.format.open_memmap(
            tmp_mmap_path,
            mode="w+",
            dtype=dtype,
            shape=(n_steps, nrow, ncol, n_features),
        )
        grid_array[:] = config.fill_value

        n_rows = table.num_rows
        pgids = table[config.pgid_field].to_numpy(
            zero_copy_only=False,
        )
        month_ids = table[config.month_id_field].to_numpy(
            zero_copy_only=False,
        )
        value_arrays = [
            table[feat.value_field].to_numpy(
                zero_copy_only=False,
            )
            for feat in config.features
        ]
        del table

        n_placed = 0
        n_skipped_spatial = 0
        n_skipped_temporal = 0

        start_year = config.temporal_config.start_year
        start_month = config.temporal_config.start_month

        for i in range(n_rows):
            pgid = pgids[i]
            if pgid < 1 or pgid > n_cells:
                n_skipped_spatial += 1
                continue

            time_idx = _month_id_to_time_index(
                month_ids[i], start_year, start_month
            )
            if time_idx < 0 or time_idx >= n_steps:
                n_skipped_temporal += 1
                continue

            pgid_idx = pgid - 1
            row = pgid_idx // ncol
            col = pgid_idx % ncol

            for feat_idx in range(n_features):
                val = value_arrays[feat_idx][i]
                if not np.isnan(val):
                    grid_array[time_idx, row, col, feat_idx] = val

            n_placed += 1

        if n_skipped_spatial > 0:
            logger.warning(
                "Skipped %d rows: pgid outside grid bounds",
                n_skipped_spatial,
            )
        if n_skipped_temporal > 0:
            logger.warning(
                "Skipped %d rows: month_id outside temporal range",
                n_skipped_temporal,
            )
        logger.info("Placed %d rows into grid", n_placed)

        feature_names = [feat.name for feat in config.features]

        pgids_flat, _, _ = generate_grid(config.grid_config)
        pgids_2d = pgids_flat.reshape(nrow, ncol)
        time_steps = generate_time_steps(config.temporal_config)

        write_compilation_output(
            grid_array=grid_array,
            pgids_2d=pgids_2d,
            time_steps=time_steps,
            feature_names=feature_names,
            output_dir=config.output_dir,
            ledger_path=config.ledger_path,
            dataset_id=DATASET_ID,
            source_path=config.source_path,
            source_digest=source_digest,
            n_placed=n_placed,
            n_skipped_spatial=n_skipped_spatial,
            n_skipped_temporal=n_skipped_temporal,
        )

        logger.info(
            "Compiled pre-gridded: shape=%s, features=%s, "
            "output=%s",
            grid_array.shape,
            feature_names,
            config.output_dir,
        )
    finally:
        if grid_array is not None:
            del grid_array
        if os.path.exists(tmp_mmap_path):
            os.unlink(tmp_mmap_path)

    return config.output_dir
